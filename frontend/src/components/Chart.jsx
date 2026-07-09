import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  BarChart,
  Bar,
  Cell
} from 'recharts';

// 1. Radar Chart for Risk Analysis
export function RiskRadarChart({ overallScore = 5 }) {
  // We can construct a beautiful radar diagram representing different risk dimensions
  const score = parseFloat(overallScore) || 5;
  const base = score * 10;
  
  const data = [
    { subject: 'Market Risk', value: Math.min(base + 12, 100), fullMark: 100 },
    { subject: 'Technical Risk', value: Math.min(base - 8, 100), fullMark: 100 },
    { subject: 'Founders Risk', value: Math.min(base - 15, 100), fullMark: 100 },
    { subject: 'Financial Risk', value: Math.min(base + 5, 100), fullMark: 100 },
    { subject: 'Execution Risk', value: Math.min(base + 10, 100), fullMark: 100 },
  ];

  return (
    <div className="h-64 w-full flex items-center justify-center">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" r="80%" data={data}>
          <PolarGrid stroke="#1e1e24" />
          <PolarAngleAxis dataKey="subject" tick={{ fill: '#9ca3af', fontSize: 10 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#6b7280' }} />
          <Radar
            name="Risk Level"
            dataKey="value"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.25}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

// 2. Area Chart for Market Sizing / Growth
export function MarketSizeChart({ revenue = 10, growth = 20 }) {
  // Project revenue projections over 5 years
  const startRev = parseFloat(revenue) || 10;
  const growthRate = (parseFloat(growth) || 20) / 100;

  const data = Array.from({ length: 5 }, (_, idx) => {
    const year = new Date().getFullYear() + idx;
    const projectedRev = startRev * Math.pow(1 + growthRate, idx);
    return {
      name: `Yr ${idx + 1} (${year})`,
      Revenue: parseFloat(projectedRev.toFixed(2)),
      MarketShare: parseFloat((projectedRev * 1.5).toFixed(2)),
    };
  });

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorShare" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <XAxis dataKey="name" stroke="#6b7280" fontSize={10} tickLine={false} />
          <YAxis stroke="#6b7280" fontSize={10} tickLine={false} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#0c0c0e', borderColor: '#1c1c22', borderRadius: '12px' }}
            itemStyle={{ color: '#f3f4f6' }}
            labelStyle={{ color: '#9ca3af' }}
          />
          <Area type="monotone" dataKey="Revenue" stroke="#8b5cf6" fillOpacity={1} fill="url(#colorRev)" strokeWidth={2} />
          <Area type="monotone" dataKey="MarketShare" stroke="#3b82f6" fillOpacity={1} fill="url(#colorShare)" strokeWidth={1.5} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// 3. Bar Chart for ML confidence index
export function MLConfidenceChart({ probability = 75 }) {
  const prob = parseFloat(probability) || 75;
  
  const data = [
    { name: 'Model Prediction', value: prob },
    { name: 'Industry Average', value: 45 },
    { name: 'Target Threshold', value: 65 },
  ];

  const COLORS = ['#8b5cf6', '#4b5563', '#10b981'];

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 20, right: 10, left: -20, bottom: 5 }}
        >
          <XAxis dataKey="name" stroke="#6b7280" fontSize={10} tickLine={false} />
          <YAxis domain={[0, 100]} stroke="#6b7280" fontSize={10} tickLine={false} />
          <Tooltip
            contentStyle={{ backgroundColor: '#0c0c0e', borderColor: '#1c1c22', borderRadius: '12px' }}
            itemStyle={{ color: '#f3f4f6' }}
            labelStyle={{ color: '#9ca3af' }}
          />
          <Bar dataKey="value" radius={[8, 8, 0, 0]} barSize={40}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
