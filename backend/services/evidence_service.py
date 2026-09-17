"""
Evidence Service

Provides reusable helpers for building evidence lookups, resolving LLM-provided
evidence IDs to actual EvidenceRecord objects, validating FactTypes, and calculating
deterministic evidence confidence scores.
"""

from typing import Dict, List, Optional, Tuple, Set
from core.logging import app_logger
from schemas.evidence import EvidenceRecord, FactType, SourceCredibility


def build_evidence_lookup(
    evidence_records: List[EvidenceRecord]
) -> Dict[str, EvidenceRecord]:
    """
    Builds a dictionary mapping evidence_id -> EvidenceRecord for fast, safe resolution.
    """
    lookup: Dict[str, EvidenceRecord] = {}
    if not evidence_records:
        return lookup

    for record in evidence_records:
        if record and record.evidence_id:
            lookup[record.evidence_id] = record
    return lookup


def validate_fact_type(raw_fact_type: Optional[str]) -> FactType:
    """
    Safely validates a raw fact_type string from LLM output.
    Returns the matching FactType enum value, or FactType.UNKNOWN if invalid/missing.
    """
    if not raw_fact_type or not isinstance(raw_fact_type, str):
        return FactType.UNKNOWN

    cleaned = raw_fact_type.strip().upper()
    try:
        return FactType(cleaned)
    except ValueError:
        app_logger.warning(
            f"[EvidenceService] Invalid fact_type '{raw_fact_type}' received from LLM. "
            f"Falling back to FactType.UNKNOWN."
        )
        return FactType.UNKNOWN


def resolve_evidence_ids(
    primary_evidence_id: Optional[str],
    corroborating_evidence_ids: Optional[List[str]],
    evidence_lookup: Dict[str, EvidenceRecord]
) -> Tuple[Optional[EvidenceRecord], List[EvidenceRecord]]:
    """
    Resolves evidence IDs provided by the LLM against the actual Python evidence_lookup map.

    Rules:
    1. Valid primary ID -> attaches matching EvidenceRecord.
    2. Invalid primary ID -> primary_evidence = None (logs warning, never invents evidence).
    3. Valid corroborating IDs -> attaches matching EvidenceRecords.
    4. Invalid corroborating IDs -> ignored safely.
    5. Deduplication -> removes duplicate IDs and primary ID from corroborating list.
    """
    primary_record: Optional[EvidenceRecord] = None
    corroborating_records: List[EvidenceRecord] = []
    seen_ids: Set[str] = set()

    # 1. Resolve Primary Evidence
    if primary_evidence_id and isinstance(primary_evidence_id, str):
        pid = primary_evidence_id.strip()
        if pid in evidence_lookup:
            primary_record = evidence_lookup[pid]
            seen_ids.add(pid)
        else:
            app_logger.warning(
                f"[EvidenceService] Primary evidence ID '{primary_evidence_id}' not found in lookup. "
                f"Setting primary_evidence to None."
            )

    # 2. Resolve Corroborating Evidence
    if corroborating_evidence_ids and isinstance(corroborating_evidence_ids, list):
        for cid in corroborating_evidence_ids:
            if not cid or not isinstance(cid, str):
                continue
            clean_cid = cid.strip()
            if clean_cid in seen_ids:
                continue  # Skip duplicate or primary ID
            if clean_cid in evidence_lookup:
                corroborating_records.append(evidence_lookup[clean_cid])
                seen_ids.add(clean_cid)
            else:
                app_logger.warning(
                    f"[EvidenceService] Corroborating evidence ID '{clean_cid}' not found in lookup. Ignoring."
                )

    return primary_record, corroborating_records


def calculate_evidence_confidence(
    primary_evidence: Optional[EvidenceRecord],
    corroborating_evidence: List[EvidenceRecord]
) -> float:
    """
    Calculates a deterministic evidence confidence score (0.0 to 1.0) based on source credibility
    and genuine independent corroboration.

    Baseline mapping by primary credibility:
    - HIGH    -> 0.85
    - MEDIUM  -> 0.65
    - LOW     -> 0.40
    - UNKNOWN / None -> 0.30

    Corroboration boost (respects independence_group):
    - 1st independent source -> +0.10
    - 2nd independent source -> +0.05
    - Maximum confidence capped at 1.0
    """
    if primary_evidence is None:
        base_confidence = 0.30
        seen_groups: Set[str] = set()
    else:
        cred = primary_evidence.credibility
        if cred == SourceCredibility.HIGH:
            base_confidence = 0.85
        elif cred == SourceCredibility.MEDIUM:
            base_confidence = 0.65
        elif cred == SourceCredibility.LOW:
            base_confidence = 0.40
        else:
            base_confidence = 0.30

        # Track primary independence group or URL
        seen_groups = set()
        group_key = primary_evidence.independence_group or primary_evidence.url or primary_evidence.evidence_id
        if group_key:
            seen_groups.add(group_key.lower())

    # Calculate corroboration boost for genuinely independent sources
    independent_count = 0
    for corr in corroborating_evidence or []:
        if not corr:
            continue
        g_key = corr.independence_group or corr.url or corr.evidence_id
        if not g_key:
            continue
        g_key_lower = g_key.lower()
        if g_key_lower not in seen_groups:
            seen_groups.add(g_key_lower)
            independent_count += 1

    boost = 0.0
    if independent_count >= 1:
        boost += 0.10
    if independent_count >= 2:
        boost += 0.05

    final_confidence = min(1.0, base_confidence + boost)
    return round(final_confidence, 2)
