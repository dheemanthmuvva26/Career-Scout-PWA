// Shared profile detection logic — used by forge page, JobCard, share-target, etc.

export const PROFILES = [
  { id: "",                   label: "Auto" },
  { id: "genai_engineer",     label: "GenAI Engineer" },
  { id: "ai_developer",       label: "AI Developer" },
  { id: "ml_engineer",        label: "ML Engineer" },
  { id: "data_scientist",     label: "Data Scientist" },
  { id: "bi_developer",       label: "Data Analyst" },
  { id: "credit_analyst",     label: "Credit Analyst" },
  { id: "financial_analyst",  label: "Financial Analyst" },
  { id: "quant_analyst",      label: "Quant Analyst" },
  { id: "risk_analyst",       label: "Risk Analyst" },
  { id: "compliance_analyst", label: "Compliance Analyst" },
];

export const PROFILE_DISPLAY: Record<string, string> = Object.fromEntries(
  PROFILES.filter(p => p.id).map(p => [p.id, p.label])
);

// Mirrors backend _PROFILE_TAG_MAP — most-specific first, first match wins
const PROFILE_TAG_MAP: Record<string, string[]> = {
  genai_engineer:    ["genai", "rag", "knowledge_graph", "langchain", "vector_db", "agentic", "graph_rag"],
  ai_developer:      ["ai_engineer", "applied_ai", "nlp", "chatbot", "automation", "dialogflow"],
  ml_engineer:       ["ml", "machine_learning", "machine_learning_engineer", "deep_learning", "pytorch", "tensorflow", "model_training"],
  credit_analyst:    ["credit_risk", "credit_analyst", "underwriting", "lending", "loan_analysis", "credit_scoring"],
  financial_analyst: ["financial_analyst", "financial_reporting", "financial_modeling", "investment", "equity_research", "valuation", "accounting"],
  quant_analyst:     ["quant_analyst", "quantitative", "quantitative_analysis", "statistical_modeling", "econometrics", "actuarial"],
  risk_analyst:      ["risk_analyst", "risk", "risk_management", "market_risk", "operational_risk", "banking"],
  compliance_analyst:["compliance", "regulatory", "aml", "audit", "kyc", "financial_crime"],
  data_scientist:    ["data_scientist", "predictive_modeling", "statistical_analysis"],
  bi_developer:      ["bi_developer", "bi", "data_analyst", "reporting", "dashboard", "visualization", "business_intelligence"],
};

const DESC_KEYWORDS: Record<string, string[]> = {
  genai_engineer:    ["rag", "llm", "langchain", "vector", "embedding", "generative", "knowledge graph", "agentic", "large language"],
  ai_developer:      ["artificial intelligence", "chatbot", "conversational", "nlp", "natural language", "automation", "dialogflow"],
  ml_engineer:       ["machine learning", "deep learning", "pytorch", "tensorflow", "model training", "mlops", "neural network"],
  data_scientist:    ["data scientist", "predictive", "statistical analysis", "eda", "experiment", "hypothesis"],
  bi_developer:      ["data analyst", "dashboard", "power bi", "tableau", "reporting", "business intelligence", "kpi", "sql analyst"],
  credit_analyst:    ["credit", "underwriting", "lending", "loan", "credit risk", "credit scoring", "nbfc"],
  financial_analyst: ["financial analyst", "financial model", "valuation", "equity research", "investment banking", "accounting", "p&l", "10-k"],
  quant_analyst:     ["quantitative", "quant", "statistical model", "algorithmic", "econometrics", "derivatives", "actuar"],
  risk_analyst:      ["risk management", "market risk", "operational risk", "risk framework", "risk officer", "risk assessment"],
  compliance_analyst:["compliance", "regulatory", "aml", "kyc", "audit", "financial crime", "anti-money"],
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
