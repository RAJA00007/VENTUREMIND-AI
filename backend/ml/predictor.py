import math
import joblib
import pandas as pd
from pathlib import Path
from core.logging import app_logger

BASE_DIR = Path(__file__).parent


class ModelLoadError(RuntimeError):
    """Raised when ML model artifacts cannot be loaded."""
    pass


class StartupPredictor:

    def __init__(self):
        self._model = None
        self._encoder = None

    def _ensure_loaded(self):
        if self._model is not None and self._encoder is not None:
            return

        model_path = BASE_DIR / "startup_success_model.pkl"
        encoder_path = BASE_DIR / "industry_encoder.pkl"

        if not model_path.exists() or not encoder_path.exists():
            raise ModelLoadError(
                f"ML model artifacts not found at {BASE_DIR}. "
                f"Please ensure startup_success_model.pkl and industry_encoder.pkl exist."
            )

        try:
            self._model = joblib.load(model_path)
            self._encoder = joblib.load(encoder_path)
        except Exception as exc:
            app_logger.error(f"[StartupPredictor] Failed to load ML model artifacts: {exc}")
            raise ModelLoadError(
                f"Failed to load ML model artifacts: {exc}"
            ) from exc

    def predict(
        self,
        industry: str,
        funding: float,
        employees: int,
        age: int,
        revenue: float,
        growth: float
    ):
        self._ensure_loaded()

        def _clean_float(val, name, default=0.0):
            if val is None:
                return default
            try:
                fval = float(val)
                if math.isnan(fval) or math.isinf(fval):
                    app_logger.warning(f"[StartupPredictor] Invalid float {val} for {name}, defaulting to {default}")
                    return default
                return fval
            except (ValueError, TypeError):
                app_logger.warning(f"[StartupPredictor] Non-numeric float {val} for {name}, defaulting to {default}")
                return default

        def _clean_int(val, name, default=0):
            if val is None:
                return default
            try:
                fval = float(val)
                if math.isnan(fval) or math.isinf(fval):
                    app_logger.warning(f"[StartupPredictor] Invalid int {val} for {name}, defaulting to {default}")
                    return default
                return int(fval)
            except (ValueError, TypeError):
                app_logger.warning(f"[StartupPredictor] Non-numeric int {val} for {name}, defaulting to {default}")
                return default

        funding_clean = _clean_float(funding, "funding_million")
        revenue_clean = _clean_float(revenue, "revenue_million")
        growth_clean = _clean_float(growth, "growth_rate")
        employees_clean = _clean_int(employees, "employees")
        age_clean = _clean_int(age, "age_years")
        industry_str = str(industry) if industry is not None else "AI"

        try:
            industry_encoded = self._encoder.transform([industry_str])[0]
        except Exception:
            industry_encoded = 0

        # DataFrame schema strictly matching train_model.py
        data = pd.DataFrame(
            [
                {
                    "industry": industry_encoded,
                    "funding_million": funding_clean,
                    "employees": employees_clean,
                    "age_years": age_clean,
                    "revenue_million": revenue_clean,
                    "growth_rate": growth_clean
                }
            ]
        )

        try:
            probability = self._model.predict_proba(data)[0][1]
            prediction = self._model.predict(data)[0]
        except Exception as exc:
            app_logger.error(f"[StartupPredictor] Model inference failed: {exc}")
            raise RuntimeError(f"ML model inference failed: {exc}") from exc

        return {
            "success_probability": round(probability * 100, 2),
            "prediction": "Likely Success" if prediction == 1 else "High Risk"
        }


_predictor_instance = None

def get_predictor() -> StartupPredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = StartupPredictor()
    return _predictor_instance


class _LazyPredictorProxy:
    def predict(self, *args, **kwargs):
        return get_predictor().predict(*args, **kwargs)

startup_predictor = _LazyPredictorProxy()