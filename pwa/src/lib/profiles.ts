// Shared profile detection logic — used by forge page, JobCard, share-target, etc.

export const PROFILES = [
  { id: "",                      label: "Auto" },
  // ── AI / Tech ──
  { id: "genai_engineer",        label: "GenAI Engineer" },
  { id: "applied_ai_engineer",   label: "Applied AI Engineer" },
  { id: "ai_researcher",         label: "AI Research Engineer" },
  { id: "mlops_engineer",        label: "MLOps Engineer" },
  { id: "ai_engineer",           label: "AI Engineer" },
  { id: "ai_developer",          label: "AI Developer" },
  { id: "ml_engineer",           label: "ML Engineer" },
  { id: "data_engineer",         label: "Data Engineer" },
  { id: "data_scientist",        label: "Data Scientist" },
  { id: "bi_developer",          label: "Data Analyst" },
  // ── Finance ──
  { id: "investment_banking",    label: "IB Analyst" },
  { id: "fpa_analyst",           label: "FP&A Analyst" },
  { id: "research_analyst",      label: "Research Analyst" },
  { id: "treasury_analyst",      label: "Treasury Analyst" },
  { id: "audit_analyst",         label: "Audit Analyst" },
  { id: "tax_analyst",           label: "Tax Analyst" },
  { id: "credit_analyst",        label: "Credit Analyst" },
  { id: "quant_analyst",         label: "Quant Analyst" },
  { id: "financial_analyst",     label: "Financial Analyst" },
  { id: "risk_analyst",          label: "Risk Analyst" },
  { id: "compliance_analyst",    label: "Compliance Analyst" },
];

export const PROFILE_DISPLAY: Record<string, string> = Object.fromEntries(
  PROFILES.filter(p => p.id).map(p => [p.id, p.label])
);

// Mirrors backend _PROFILE_TAG_MAP — most-specific first, first match wins
const PROFILE_TAG_MAP: Record<string, string[]> = {
  // ── AI / Tech ──
  genai_engineer:      ["genai", "rag", "knowledge_graph", "langchain", "vector_db", "agentic", "graph_rag"],
  applied_ai_engineer: ["applied_ai_engineer", "applied_ai", "applied_ml", "ai_solutions", "ai_product", "applied_machine_learning", "real_world_ai", "industry_ai"],
  ai_researcher:       ["ai_researcher", "ai_research", "research_engineer", "ml_research", "research_scientist", "ai_lab", "applied_research", "model_research"],
  mlops_engineer:      ["mlops_engineer", "mlops", "ml_platform", "model_deployment", "model_monitoring", "ml_pipeline", "feature_store", "model_registry", "cicd_ml"],
  ai_engineer:         ["ai_engineer", "artificial_intelligence", "ai_system", "ai_integration", "intelligent_systems", "ai_solution", "ai_platform"],
  ai_developer:        ["applied_ai", "chatbot", "automation", "dialogflow", "conversational_ai"],
  ml_engineer:         ["ml", "machine_learning", "machine_learning_engineer", "deep_learning", "pytorch", "tensorflow", "model_training"],
  data_engineer:       ["data_engineer", "data_engineering", "etl", "data_pipeline", "spark", "airflow", "kafka", "dbt", "data_warehouse", "bigquery"],
  data_scientist:      ["data_scientist", "predictive_modeling", "statistical_analysis"],
  bi_developer:        ["bi_developer", "bi", "data_analyst", "reporting", "dashboard", "visualization", "business_intelligence"],
  // ── Finance ──
  investment_banking:  ["investment_banking", "ib_analyst", "mergers_acquisitions", "ma", "deal_structuring", "pitchbook", "dcf", "lbo", "capital_markets"],
  fpa_analyst:         ["fpa", "fpa_analyst", "financial_planning", "budgeting", "forecasting", "variance_analysis", "management_reporting", "planning_analysis"],
  research_analyst:    ["research_analyst", "investment_research", "industry_research", "sector_analysis", "company_analysis", "fundamental_analysis", "market_research"],
  treasury_analyst:    ["treasury_analyst", "treasury", "cash_management", "liquidity", "forex", "fx_management", "working_capital", "cash_flow"],
  audit_analyst:       ["audit_analyst", "internal_audit", "internal_auditor", "sox", "controls_testing", "audit_report", "process_audit", "risk_controls"],
  tax_analyst:         ["tax_analyst", "tax_compliance", "gst", "income_tax", "tax_planning", "direct_tax", "indirect_tax", "tax_filing"],
  credit_analyst:      ["credit_risk", "credit_analyst", "underwriting", "lending", "loan_analysis", "credit_scoring"],
  quant_analyst:       ["quant_analyst", "quantitative", "quantitative_analysis", "statistical_modeling", "econometrics", "actuarial"],
  financial_analyst:   ["financial_analyst", "financial_reporting", "financial_modeling", "investment", "equity_research", "valuation", "accounting"],
  risk_analyst:        ["risk_analyst", "risk", "risk_management", "market_risk", "operational_risk", "banking"],
  compliance_analyst:  ["compliance", "regulatory", "aml", "audit", "kyc", "financial_crime"],
};

const DESC_KEYWORDS: Record<string, string[]> = {
  // ── AI / Tech ──
  genai_engineer:      ["rag", "llm", "langchain", "vector", "embedding", "generative", "knowledge graph", "agentic", "large language"],
  applied_ai_engineer: ["applied ai", "applied machine learning", "applied ml", "ai solution", "ai product", "ai feature", "industry ai", "real world ai"],
  ai_researcher:       ["research engineer", "ai research", "ml research", "research scientist", "ablation", "benchmark", "experiment", "publication", "paper", "model evaluation"],
  mlops_engineer:      ["mlops", "model deployment", "ml pipeline", "model monitoring", "feature store", "ml platform", "cicd ml", "model registry", "drift"],
  ai_engineer:         ["ai engineer", "artificial intelligence engineer", "intelligent system", "ai integration", "ai platform", "ai solution", "end to end ai"],
  ai_developer:        ["artificial intelligence", "chatbot", "conversational", "automation", "dialogflow", "natural language", "voice bot"],
  ml_engineer:         ["machine learning", "deep learning", "pytorch", "tensorflow", "model training", "mlops", "neural network"],
  data_engineer:       ["data engineer", "etl", "data pipeline", "spark", "airflow", "kafka", "dbt", "data warehouse", "bigquery", "orchestration"],
  data_scientist:      ["data scientist", "predictive", "statistical analysis", "eda", "experiment", "hypothesis"],
  bi_developer:        ["data analyst", "dashboard", "power bi", "tableau", "reporting", "business intelligence", "kpi", "sql analyst"],
  // ── Finance ──
  investment_banking:  ["investment banking", "m&a", "mergers and acquisitions", "pitchbook", "dcf", "lbo", "deal", "capital markets", "ib analyst"],
  fpa_analyst:         ["fp&a", "financial planning", "budgeting", "forecasting", "variance analysis", "management reporting", "planning and analysis", "budget"],
  research_analyst:    ["research analyst", "equity research", "investment research", "industry research", "sector analysis", "fundamental analysis", "company analysis"],
  treasury_analyst:    ["treasury", "cash management", "liquidity", "forex", "working capital", "cash flow", "fx", "treasury analyst"],
  audit_analyst:       ["internal audit", "audit", "sox", "controls testing", "audit report", "process audit", "risk controls", "internal auditor"],
  tax_analyst:         ["tax", "gst", "income tax", "tax compliance", "tax planning", "direct tax", "indirect tax", "tax filing"],
  credit_analyst:      ["credit", "underwriting", "lending", "loan", "credit risk", "credit scoring", "nbfc"],
  quant_analyst:       ["quantitative", "quant", "statistical model", "algorithmic", "econometrics", "derivatives", "actuar"],
  financial_analyst:   ["financial analyst", "financial model", "valuation", "equity research", "investment banking", "accounting", "p&l", "10-k"],
  risk_analyst:        ["risk management", "market risk", "operational risk", "risk framework", "risk officer", "risk assessment"],
  compliance_analyst:  ["compliance", "regulatory", "aml", "kyc", "audit", "financial crime", "anti-money"],
};

export function detectProfile(tags: string[]): { profile: string; display: string; matchedTags: string[] } {
  for (const [prof, ptags] of Object.entries(PROFILE_TAG_MAP)) {
    const hits = tags.filter(t => ptags.includes(t));
    if (hits.length > 0) return { profile: prof, display: PROFILE_DISPLAY[prof] ?? prof, matchedTags: hits };
  }
  return { profile: "default", display: "Default", matchedTags: [] };
}

export function matchByDescription(desc: string): { profile: string; display: string } | null {
  const lower = desc.toLowerCase();
  let best = "";
  let bestScore = 0;
  for (const [prof, kws] of Object.entries(DESC_KEYWORDS)) {
    const score = kws.filter(kw => lower.includes(kw)).length;
    if (score > bestScore) { bestScore = score; best = prof; }
  }
  if (bestScore > 0 && best) return { profile: best, display: PROFILE_DISPLAY[best] ?? best };
  return null;
}
