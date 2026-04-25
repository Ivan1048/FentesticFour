"""
Multi-Agent System for AI Loan Processing.
5 specialized agents coordinated by an Orchestrator.
"""

import json
import re
import time
import random
import asyncio
import base64
from typing import Dict, Any, List, Optional

# Gemini API (optional — system works with regex fallback)
try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ─────────────────────────────────────────────
# AGENT 1: Extraction Agent
# ─────────────────────────────────────────────
class ExtractionAgent:
    """Extracts structured loan data from natural language using Gemini AI or regex fallback."""

    NAME = "Extraction Agent"

    def __init__(self, gemini_client=None, model_name=None):
        self.client = gemini_client
        self.model_name = model_name

    async def process(self, text: str, existing_data: Dict[str, Any] = None,
                      file_data: str = None, file_mime: str = None, file_name: str = None) -> Dict[str, Any]:
        start = time.time()

        if self.client and file_data:
            # Multimodal: extract from uploaded document
            result = await self._extract_from_document(text, existing_data or {}, file_data, file_mime, file_name)
        elif self.client:
            result = await self._extract_with_gemini(text, existing_data or {})
        else:
            result = self._extract_with_regex(text)

        # Merge with existing data — new values override old ones
        if existing_data:
            merged = {**existing_data}
            for k, v in result.get("extracted", {}).items():
                if v is not None:
                    merged[k] = v
            result["extracted"] = merged

        elapsed = int((time.time() - start) * 1000)

        return {
            "agent_name": self.NAME,
            "status": "success",
            "message": result.get("message", "Data extracted successfully"),
            "data": result.get("extracted", {}),
            "duration_ms": elapsed,
        }

    async def _extract_with_gemini(self, text: str, existing: Dict) -> Dict:
        existing_str = json.dumps(existing) if existing else "{}"

        prompt = f"""You are a "Master Loan Extractor". Your job is to extract loan-related details from unstructured text or documents.
If a contract is provided, look for BOTH official terms (Principal, Interest, Tenure) AND borrower profile details (Monthly Income, Employment Status, Existing Debt).

Currently known data: {existing_str}

Return exactly this JSON structure (use 0/null for unknown):
{{
  "loan_type": string (e.g. "home", "personal", "car", "business" or the specific type mentioned),
  "income": number (monthly),
  "employment_status": string (e.g. "permanent" or specific term found),
  "employment_duration": number (years),
  "property_price": number,
  "existing_debt": number (monthly),
  "country": string (e.g. "Malaysia")
}}

INFERENCE RULES:
- If document mentions "Mortgage" or "Property", loan_type = "home".
- If "Hire Purchase" or "Vehicle", loan_type = "car".
- Convert any weekly/annual income to monthly.
- If "Permanent" or "Full-time", employment_status = "permanent".

Return ONLY raw JSON. No markdown. No explanation.

User message: \"{text}\""""

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
            )
            response_text = response.text.strip()
            # Strip markdown code fences if present
            response_text = re.sub(r"```json\s*", "", response_text)
            response_text = re.sub(r"```\s*", "", response_text)

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response_text)

            # Normalise values
            cleaned: Dict[str, Any] = {}
            numeric_fields = {"income", "employment_duration", "property_price", "existing_debt"}
            for k in ["loan_type", "income", "employment_status", "employment_duration", "property_price", "existing_debt"]:
                val = data.get(k)
                if val is None or val == "null":
                    continue
                if k in numeric_fields:
                    try:
                        # Strip commas, RM, $, etc.
                        clean_v = re.sub(r"[^\d.]", "", str(val))
                        cleaned[k] = float(clean_v) if clean_v else 0.0
                    except (ValueError, TypeError):
                        pass
                else:
                    cleaned[k] = str(val).lower()

            return {"extracted": cleaned, "message": "AI-powered extraction completed successfully"}

        except Exception as e:
            result = self._extract_with_regex(text)
            result["message"] = f"Gemini unavailable — used regex fallback ({str(e)[:80]})"
            return result

    async def _extract_from_document(self, text: str, existing: Dict,
                                      file_data: str, file_mime: str, file_name: str = "") -> Dict:
        """Extract loan data from an uploaded document using Gemini's multimodal capabilities."""
        existing_str = json.dumps(existing) if existing else "{}"

        prompt = f"""You are a "Master Document Extractor". Analyze the document AND the message to extract loan data.
If a contract is provided, look for BOTH official terms (Principal, Interest, Tenure) AND borrower profile details (Monthly Income, Employment Status, Existing Debt).

Currently known data: {existing_str}
User message: \"{text}\"

Return exactly this JSON structure (use 0/null for unknown):
{{
  "loan_type": string (e.g. "home", "personal", "car", "business" or the specific type mentioned),
  "income": number (monthly),
  "employment_status": string (e.g. "permanent" or specific term found),
  "employment_duration": number (years),
  "property_price": number,
  "existing_debt": number (monthly),
  "country": string (e.g. "Malaysia")
}}

Return ONLY raw JSON. No markdown. No explanation."""

        try:
            file_bytes = base64.b64decode(file_data)
            
            if file_mime == "text/plain":
                text_content = file_bytes.decode("utf-8")
                final_prompt = f"{prompt}\n\nDOCUMENT CONTENT:\n{text_content}"
                contents = [final_prompt]
            else:
                from google.genai import types
                contents = [
                    types.Content(
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=file_bytes, mime_type=file_mime),
                        ]
                    )
                ]

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
            )
            response_text = response.text.strip()
            # Strip markdown code fences if present
            response_text = re.sub(r"```json\s*", "", response_text)
            response_text = re.sub(r"```\s*", "", response_text)

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response_text)

            # Normalise values
            cleaned: Dict[str, Any] = {}
            numeric_fields = {"income", "employment_duration", "property_price", "existing_debt"}
            for k in ["loan_type", "income", "employment_status", "employment_duration", "property_price", "existing_debt"]:
                val = data.get(k)
                if val is None or val == "null":
                    continue
                if k in numeric_fields:
                    try:
                        # Strip commas, RM, $, etc.
                        clean_v = re.sub(r"[^\d.]", "", str(val))
                        cleaned[k] = float(clean_v) if clean_v else 0.0
                    except (ValueError, TypeError):
                        pass
                else:
                    cleaned[k] = str(val).lower()

            doc_type = "document"
            if file_name:
                fn = file_name.lower()
                if any(w in fn for w in ["payslip", "salary", "slip", "pay"]):
                    doc_type = "payslip"
                elif any(w in fn for w in ["bank", "statement"]):
                    doc_type = "bank statement"
                elif any(w in fn for w in ["ic", "identity", "mykad"]):
                    doc_type = "identity card"

            return {"extracted": cleaned, "message": f"📄 AI extracted data from uploaded {doc_type} successfully"}

        except Exception as e:
            # Fall back to text-only extraction
            result = self._extract_with_regex(text)
            result["message"] = f"Document analysis failed — used text fallback ({str(e)[:80]})"
            return result

    def _extract_with_regex(self, text: str) -> Dict:
        extracted: Dict[str, Any] = {}
        t = text.lower()

        # Loan type
        if any(w in t for w in ["house", "home", "property", "rumah"]):
            extracted["loan_type"] = "home"
        elif any(w in t for w in ["car", "vehicle", "kereta"]):
            extracted["loan_type"] = "car"
        elif "personal" in t:
            extracted["loan_type"] = "personal"
        elif any(w in t for w in ["business", "perniagaan"]):
            extracted["loan_type"] = "business"

        # Income
        m = re.search(r"(?:salary|income|earn|gaji|pay|make)[^\d]*(?:rm\s*)?(\d[\d,]*)", t)
        if not m:
            m = re.search(r"(?:rm\s*)?(\d[\d,]*)[^\d]*(?:salary|income|monthly|gaji|per month)", t)
        if m:
            extracted["income"] = float(m.group(1).replace(",", ""))

        # Employment status
        for status in ["permanent", "government", "self-employed", "contract", "unemployed"]:
            if status in t:
                extracted["employment_status"] = status
                break

        # Employment duration
        m = re.search(r"(\d+)\s*(?:year|tahun|yr)", t)
        if m:
            extracted["employment_duration"] = float(m.group(1))

        # Property price
        m = re.search(r"(?:house|property|price|cost|worth|value|harga)[^\d]*(?:rm\s*)?(\d[\d,]*)", t)
        if not m:
            m = re.search(r"(?:rm\s*)?(\d[\d,]*)[^\d]*(?:house|property|price)", t)
        if m:
            extracted["property_price"] = float(m.group(1).replace(",", ""))

        # Existing debt
        if any(w in t for w in ["no debt", "no existing debt", "debt free", "tiada hutang"]):
            extracted["existing_debt"] = 0.0
        else:
            m = re.search(r"(?:debt|hutang|owe|owing|commitment)[^\d]*(?:rm\s*)?(\d[\d,]*)", t)
            if m:
                extracted["existing_debt"] = float(m.group(1).replace(",", ""))

        # Country
        if any(w in t for w in ["malaysia", "kl", "selangor", "penang", "johor"]):
            extracted["country"] = "Malaysia"
        elif "singapore" in t:
            extracted["country"] = "Singapore"
        elif "thailand" in t:
            extracted["country"] = "Thailand"
        elif "indonesia" in t:
            extracted["country"] = "Indonesia"
        else:
            extracted["country"] = "Malaysia"  # Default

        return {"extracted": extracted, "message": "Regex-based extraction completed"}


# ─────────────────────────────────────────────
# AGENT 2: Validation Agent
# ─────────────────────────────────────────────
class ValidationAgent:
    """Validates extracted data and identifies missing / ambiguous fields."""

    NAME = "Validation Agent"
    REQUIRED = ["loan_type", "income", "employment_status", "property_price", "existing_debt"]
    OPTIONAL = ["employment_duration"]

    FIELD_LABELS = {
        "loan_type": "type of loan (home / personal / car / business)",
        "income": "monthly income",
        "employment_status": "employment status (permanent / government / self-employed / contract)",
        "employment_duration": "duration of employment (years)",
        "property_price": "property or asset price",
        "existing_debt": "monthly existing debt payments (or say 'no debt')",
        "country": "country (e.g. Malaysia, Singapore)",
    }

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()

        missing: List[str] = []
        warnings: List[str] = []

        for field in self.REQUIRED:
            if field not in data or data[field] is None:
                missing.append(field)

        for field in self.OPTIONAL:
            if field not in data or data[field] is None:
                warnings.append(f"Optional field '{field}' not provided — defaults may apply")

        # Range checks
        if "income" in data and data["income"] is not None:
            if data["income"] < 0:
                missing.append("income (invalid: negative)")
            elif data["income"] < 500:
                warnings.append("Income seems unusually low — please double-check")

        if "property_price" in data and data["property_price"] is not None and data["property_price"] < 0:
            missing.append("property_price (invalid: negative)")

        elapsed = int((time.time() - start) * 1000)

        if missing:
            friendly = [self.FIELD_LABELS.get(f, f) for f in missing]
            return {
                "agent_name": self.NAME,
                "status": "warning",
                "message": f"Please provide: {', '.join(friendly)}",
                "data": {"missing_fields": missing, "warnings": warnings},
                "duration_ms": elapsed,
            }

        return {
            "agent_name": self.NAME,
            "status": "success",
            "message": "All required fields validated ✓",
            "data": {"missing_fields": [], "warnings": warnings},
            "duration_ms": elapsed,
        }


# ─────────────────────────────────────────────
# AGENT 3: Financial Analysis Agent
# ─────────────────────────────────────────────
class FinancialAnalysisAgent:
    """Calculates monthly repayment, DSR, and risk categorisation."""

    NAME = "Financial Analysis Agent"

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()

        income = data.get("income", 0)
        property_price = data.get("property_price", 0)
        existing_debt = data.get("existing_debt", 0)

        # ── Step 4: Financial Estimation ──
        # Use synthesized contract data if available, otherwise use defaults
        loan_amount = data.get("loan_amount") or (property_price * 0.9)
        
        # Determine Rate
        annual_rate = 0.0575 # Default (5.75%)
        custom_rate = data.get("interest_rate")
        loan_type = str(data.get("loan_type", "")).lower()
        
        if custom_rate:
            # Convert 5.5 to 0.055
            annual_rate = float(custom_rate) / 100 if float(custom_rate) >= 1 else float(custom_rate)
        elif "home" in loan_type or "mortgage" in loan_type:
            annual_rate = 0.042
        elif "car" in loan_type or "vehicle" in loan_type or "hire" in loan_type:
            annual_rate = 0.032
        elif "personal" in loan_type:
            annual_rate = 0.075
        elif "business" in loan_type:
            annual_rate = 0.065

        # Determine Tenure
        tenure_months = 360 # Default (30 years)
        custom_tenure = data.get("tenure")
        if custom_tenure:
            # Logic: If > 50, assume months, otherwise assume years
            val = float(custom_tenure)
            tenure_months = int(val if val > 10 else val * 12)
        elif "car" in loan_type:
            tenure_months = 108 # 9 years
        elif "personal" in loan_type:
            tenure_months = 60 # 5 years
            
        monthly_rate = annual_rate / 12
        n = tenure_months

        if monthly_rate > 0 and n > 0:
            monthly_installment = (loan_amount * monthly_rate * (1 + monthly_rate)**n) / ((1 + monthly_rate)**n - 1)
        else:
            monthly_installment = loan_amount / max(n, 1)

        total_monthly_debt = monthly_installment + existing_debt
        dsr = (total_monthly_debt / income * 100) if income > 0 else 100.0

        if dsr < 40:
            risk = "Low Risk"
            msg = f"DSR of {dsr:.2f}% is well within Bank Negara Malaysia (BNM) recommended safety limits (< 60%)."
        elif dsr <= 70:
            risk = "Medium Risk"
            msg = f"DSR of {dsr:.2f}% is at the upper bound of standard BNM guidelines (limit ~60-70%). Requires closer credit score scrutiny."
        else:
            risk = "High Risk"
            msg = f"DSR of {dsr:.2f}% exceeds BNM's prudent debt-to-income limits. Significant risk of default detected."

        elapsed = int((time.time() - start) * 1000)

        return {
            "agent_name": self.NAME,
            "status": "success",
            "message": msg,
            "data": {
                "monthly_installment": round(monthly_installment, 2),
                "total_monthly_debt": round(total_monthly_debt, 2),
                "dsr": round(dsr, 2),
                "risk_level": risk,
                "loan_amount": round(loan_amount, 2),
                "tenure_years": 30,
                "interest_rate": "4.0%",
            },
            "duration_ms": elapsed,
        }


# ─────────────────────────────────────────────
# AGENT 4: Credit Check Agent
# ─────────────────────────────────────────────
class CreditCheckAgent:
    """Simulates credit-score lookup and property valuation."""

    NAME = "Credit Check Agent"

    async def process(self, data: Dict[str, Any], dsr: float, risk_level: str) -> Dict[str, Any]:
        start = time.time()

        employment = data.get("employment_status", "unknown")
        duration = data.get("employment_duration", 0) or 0

        # ── Credit score simulation ──
        if dsr > 60:
            credit = "poor"
        elif dsr > 40:
            credit = "average" if employment in ("contract", "self-employed") else "good"
        else:
            credit = "good" if (duration >= 3 or employment in ("permanent", "government")) else "average"

        # ── Property valuation simulation ──
        property_price = data.get("property_price", 0)
        factor = random.uniform(0.92, 1.10)
        estimated = round(property_price * factor, 2)

        if estimated >= property_price:
            val_result = "above asking price"
        elif estimated >= property_price * 0.95:
            val_result = "fair"
        else:
            val_result = "below asking price"

        elapsed = int((time.time() - start) * 1000)

        return {
            "agent_name": self.NAME,
            "status": "success",
            "message": f"Credit: {credit.upper()} | Valuation: {val_result}",
            "data": {
                "credit_score": credit,
                "estimated_value": estimated,
                "valuation_result": val_result,
                "credit_factors": {
                    "dsr_impact": risk_level,
                    "employment_stability": "stable" if employment in ("permanent", "government") else "moderate",
                    "employment_tenure": f"{duration} years" if duration else "N/A",
                },
            },
            "duration_ms": elapsed,
        }


# ─────────────────────────────────────────────
# AGENT 5: Decision Agent
# ─────────────────────────────────────────────
class DecisionAgent:
    """Final loan-approval decision engine."""

    NAME = "Decision Agent"

    async def process(self, risk_level: str, credit_score: str, valuation: str, dsr: float) -> Dict[str, Any]:
        start = time.time()

        # ── Decision matrix ──
        if risk_level == "Low Risk" and credit_score == "good":
            status, action, msg = (
                "Pre-Approved",
                "Proceed to document submission",
                "Congratulations! Your application is BNM-compliant and pre-approved based on standard credit guidelines.",
            )
        elif risk_level == "Low Risk" and credit_score == "average":
            status, action, msg = (
                "Conditional Approval",
                "Submit additional income documentation",
                "Your application shows promise. Additional documentation required.",
            )
        elif risk_level == "Medium Risk" and credit_score in ("good", "average"):
            status, action, msg = (
                "Conditional Approval",
                "Manual review by senior officer — additional guarantor may be required",
                "Your application requires further review. A relationship manager will contact you.",
            )
        elif risk_level == "Medium Risk" and credit_score == "poor":
            status, action, msg = (
                "Manual Review Required",
                "Escalate to risk assessment team",
                "Your application has been flagged for detailed risk assessment.",
            )
        elif risk_level == "High Risk" and credit_score == "poor":
            status, action, msg = (
                "Rejected",
                "Improve DSR by reducing debts before reapplying",
                "Application rejected as it exceeds the risk appetite defined by our BNM-aligned credit policy.",
            )
        elif risk_level == "High Risk":
            status, action, msg = (
                "Manual Review Required",
                "Escalate to senior risk committee",
                "Your application requires review by the senior risk committee.",
            )
        else:
            status, action, msg = (
                "Manual Review Required",
                "Escalate for further assessment",
                "Your application needs additional review.",
            )

        # Adjust for property valuation
        if valuation == "below asking price" and status == "Pre-Approved":
            status = "Conditional Approval"
            action = "Property re-valuation required"
            msg += " Note: Property valuation came in below asking price."

        elapsed = int((time.time() - start) * 1000)

        s = "success" if status in ("Pre-Approved", "Conditional Approval") else ("warning" if status == "Manual Review Required" else "error")

        return {
            "agent_name": self.NAME,
            "status": s,
            "message": msg,
            "data": {
                "loan_status": status,
                "next_action": action,
                "decision_factors": {
                    "risk_level": risk_level,
                    "credit_score": credit_score,
                    "valuation": valuation,
                    "dsr": f"{dsr:.2f}%",
                },
            },
            "duration_ms": elapsed,
        }


# ─────────────────────────────────────────────
# AGENT 6: Legal Compliance Agent (MCP Tool)
# ─────────────────────────────────────────────
class LegalComplianceAgent:
    """Verifies loan adherence to regional laws (e.g. BNM DSR caps)."""

    NAME = "Legal Compliance Agent"

    # Mock Legislation Database (In a real MCP, this would be a tool)
    LEGISLATION = {
        "Malaysia": {
            "max_dsr": 70.0,
            "min_income": 3000.0,
            "max_tenure_personal": 10,
            "max_tenure_home": 35,
            "interest_cap": 18.0,
        },
        "Singapore": {
            "max_dsr": 60.0,
            "min_income": 2500.0,
            "interest_cap": 4.0,
        }
    }

    async def process(self, data: Dict[str, Any], dsr: float) -> Dict[str, Any]:
        start = time.time()
        country = data.get("country", "Malaysia")
        loan_type = data.get("loan_type", "personal")
        income = data.get("income", 0)

        rules = self.LEGISLATION.get(country, self.LEGISLATION["Malaysia"])
        violations = []

        # Check DSR cap
        if dsr > rules["max_dsr"]:
            violations.append(f"DSR of {dsr:.1f}% exceeds {country}'s regulatory limit of {rules['max_dsr']}%")

        # Check min income for specific countries
        if income < rules["min_income"]:
            violations.append(f"Monthly income RM{income} is below the {country} regulatory threshold of RM{rules['min_income']}")

        elapsed = int((time.time() - start) * 1000)

        if violations:
            return {
                "agent_name": self.NAME,
                "status": "error",
                "message": f"Legal violations found: {'; '.join(violations)}",
                "data": {
                    "violations": violations,
                    "jurisdiction": country,
                    "compliance_score": 0,
                },
                "duration_ms": elapsed,
            }

        return {
            "agent_name": self.NAME,
            "status": "success",
            "message": f"Loan is compliant with {country} laws ✓",
            "data": {
                "violations": [],
                "jurisdiction": country,
                "compliance_score": 100,
            },
            "duration_ms": elapsed,
        }


# ─────────────────────────────────────────────
# AGENT 7: Contract Analysis Agent
# ─────────────────────────────────────────────
class ContractAnalysisAgent:
    """Analyzes uploaded contract documents for legal 'traps' and safety."""

    NAME = "Contract Analysis Agent"

    def __init__(self, gemini_client=None, model_name=None):
        self.client = gemini_client
        self.model_name = model_name

    async def process(self, file_data: str, file_mime: str, country: str = "Malaysia") -> Dict[str, Any]:
        start = time.time()
        
        if not self.client or not file_data:
            return {
                "agent_name": self.NAME,
                "status": "skipped",
                "message": "No contract file provided for analysis.",
                "data": {},
                "duration_ms": 0,
            }

        prompt = f"""You are a specialized Legal Review Agent for loan contracts in {country}.
Analyze the attached contract document and identify any 'traps', predatory clauses, or safety concerns.

Check specifically for:
1. Interest Rate Traps: Hidden compounding or rates exceeding local legal caps.
2. Predatory Late Fees: Fees that are disproportionately high.
3. Early Settlement Penalties: Excessive charges for paying off the loan early.
4. Ambiguous Terms: Language that is intentionally confusing or one-sided.
5. Overall Safety Score: (0-100).

Return ONLY a raw JSON object with these keys:
- traps_found: ["description of trap 1", ...]
- safety_score: number
- risk_level: "Safe" | "Caution" | "Dangerous"
- summary: "Short summary of the contract's safety"
- loan_amount: number (principal amount)
- interest_rate: number (percent p.a.)
- tenure: number (in months)

No markdown, no explanation."""

        try:
            file_bytes = base64.b64decode(file_data)
            
            if file_mime == "text/plain":
                # For plain text files, we decode and send as text prompt
                text_content = file_bytes.decode("utf-8")
                final_prompt = f"{prompt}\n\nCONTRACT CONTENT:\n{text_content}"
                contents = [final_prompt]
            else:
                # For images/PDFs, we use multimodal parts
                from google.genai import types
                contents = [
                    types.Content(
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=file_bytes, mime_type=file_mime),
                        ]
                    )
                ]

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=contents,
            )
            data = json.loads(re.search(r"\{.*\}", response.text.strip(), re.DOTALL).group())
            
            elapsed = int((time.time() - start) * 1000)
            status = "success" if data.get("safety_score", 100) > 70 else "warning"
            if data.get("safety_score", 100) < 40: status = "error"

            return {
                "agent_name": self.NAME,
                "status": status,
                "message": data.get("summary", "Analysis complete"),
                "data": data,
                "duration_ms": elapsed,
            }

        except Exception as e:
            return {
                "agent_name": self.NAME,
                "status": "error",
                "message": f"Contract analysis failed: {str(e)[:80]}",
                "data": {"error": str(e)},
                "duration_ms": int((time.time() - start) * 1000),
            }


# ─────────────────────────────────────────────
# ORCHESTRATOR — coordinates the pipeline
# ─────────────────────────────────────────────
class OrchestratorAgent:
    """Master agent that coordinates the 5-agent loan processing pipeline."""

    def __init__(self, api_key: str = None):
        self.client = None
        self.model_name = "gemini-2.0-flash"
        if api_key and GEMINI_AVAILABLE:
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception:
                self.client = None

        self.extraction = ExtractionAgent(self.client, self.model_name)
        self.validation = ValidationAgent()
        self.financial = FinancialAnalysisAgent()
        self.credit = CreditCheckAgent()
        self.legal = LegalComplianceAgent()
        self.contract_agent = ContractAnalysisAgent(self.client, self.model_name)
        self.decision = DecisionAgent()

    async def process(self, text: str, existing_data: Dict[str, Any] = None,
                      file_data: str = None, file_mime: str = None, file_name: str = None) -> Dict[str, Any]:
        trace: List[Dict[str, Any]] = []

        # ── Step 1: Extraction ──
        ext = await self.extraction.process(text, existing_data, file_data, file_mime, file_name)
        trace.append(ext)
        extracted = ext["data"]

        # ── Step 2: NEW: EARLY Contract Discovery ──
        # We run this BEFORE financial agent so we can use the REAL terms found in the doc
        contract_res = {"status": "skipped", "message": "No contract analyzed", "data": {}}
        if file_data:
            contract_res = await self.contract_agent.process(file_data, file_mime, extracted.get("country", "Malaysia"))
            trace.append(contract_res)
            
            # AUTOMATION: Synthesis found terms into our active data
            c_data = contract_res.get("data", {})
            if c_data.get("loan_amount"):
                extracted["loan_amount"] = c_data["loan_amount"]
                if not extracted.get("property_price"):
                    extracted["property_price"] = c_data["loan_amount"]
            if c_data.get("interest_rate"):
                extracted["interest_rate"] = c_data["interest_rate"]
            if c_data.get("tenure"):
                extracted["tenure"] = c_data["tenure"]

        # ── Step 3: Validation ──
        val = await self.validation.process(extracted)
        trace.append(val)
        missing = val["data"].get("missing_fields", [])

        # ── Step 4: Financial Analysis (Now with Discovery Data) ──
        fin = await self.financial.process(extracted)
        trace.append(fin)
        dsr = fin["data"]["dsr"]
        risk = fin["data"]["risk_level"]

        # ── Step 5: Credit Check ──
        cred = await self.credit.process(extracted, dsr, risk)
        trace.append(cred)
        credit_score = cred["data"]["credit_score"]
        valuation = cred["data"]["valuation_result"]

        # ── Step 6: Legal Compliance ──
        leg = await self.legal.process(extracted, dsr)
        trace.append(leg)
        legal_status = leg["message"]

        # ── Step 7: Decision ──
        dec = await self.decision.process(risk, credit_score, valuation, dsr)
        trace.append(dec)

        # Determine overall status message
        user_message = dec["message"]
        if missing:
            user_message = f"I've analyzed your context and documents. While I'm still missing some profile details ({', '.join(missing)}), here is what I've found so far:"
        
        return {
            "intent": "Loan Application",
            "extracted_data": {
                **extracted,
                "monthly_installment": fin["data"]["monthly_installment"],
                "loan_amount": fin["data"].get("loan_amount", extracted.get("loan_amount")),
                "country": extracted.get("country", "Malaysia"),
            },
            "missing_fields": missing,
            "dsr": f"{dsr:.2f}%",
            "risk_level": risk,
            "loan_status": "Incomplete" if missing else dec["data"]["loan_status"],
            "credit_score": credit_score,
            "valuation_result": valuation,
            "legal_status": legal_status,
            "contract_safe_check": contract_res["message"],
            "next_action": "Provide missing info: " + ", ".join(missing) if missing else dec["data"]["next_action"],
            "user_message": user_message,
            "agent_trace": trace,
        }
