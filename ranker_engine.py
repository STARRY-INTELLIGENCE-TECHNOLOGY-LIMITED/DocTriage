from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Iterable, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from config import Settings, get_settings
from meta_profiler import DocumentProfile

CategoryName = Literal[
    "Architecture",
    "Design",
    "Implementation",
    "Operations",
    "CaseStudy",
    "Research",
    "Business",
    "Thinking",
    "Series",
    "LowQuality",
]


class SeriesGroup(BaseModel):
    name: str = ""
    files: list[str] = Field(default_factory=list)
    signal: str = ""


class ManifestResult(BaseModel):
    series_files: list[str] = Field(default_factory=list)
    series_groups: list[SeriesGroup] = Field(default_factory=list)
    high_value_candidates: list[str] = Field(default_factory=list)
    reasoning: str = ""

    def is_series_candidate(self, file_name: str) -> bool:
        return file_name in set(self.series_files)


class SemanticScore(BaseModel):
    quality: int = Field(default=0, ge=0, le=100)
    category: CategoryName = "LowQuality"
    document_kind: str = "Unknown"
    topic_tags: list[str] = Field(default_factory=list)
    summary: str = ""
    knowledge_density: int = Field(default=0, ge=0, le=100)
    implementation_specificity: int = Field(default=0, ge=0, le=100)
    logical_structure: int = Field(default=0, ge=0, le=100)
    evidence_richness: int = Field(default=0, ge=0, le=100)
    actionability: int = Field(default=0, ge=0, le=100)
    strategic_value: int = Field(default=0, ge=0, le=100)
    freshness: int = Field(default=0, ge=0, le=100)
    uniqueness: int = Field(default=0, ge=0, le=100)
    sensitivity_risk: int = Field(default=0, ge=0, le=100)
    public_writing_suitability: int = Field(default=0, ge=0, le=100)
    reason: str = ""

    @field_validator("document_kind", mode="before")
    @classmethod
    def _validate_document_kind(cls, value: Any) -> str:
        return _normalize_document_kind(value)

    @field_validator("topic_tags", mode="before")
    @classmethod
    def _validate_topic_tags(cls, value: Any) -> list[str]:
        return _normalize_topic_tags(value)

    @field_validator("summary", mode="before")
    @classmethod
    def _validate_summary(cls, value: Any) -> str:
        return _normalize_summary(value)


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        endpoint = self.settings.LLM_ENDPOINT.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if self.settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {self.settings.LLM_API_KEY}"

        payload = self._build_payload(endpoint, system_prompt, user_prompt)
        last_error: Exception | None = None
        for attempt in range(self.settings.LLM_RETRY_COUNT + 1):
            try:
                response = httpx.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.settings.LLM_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                response_json = response.json()
                content = self._extract_content(response_json)
                parsed = self._extract_json(content)
                break
            except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt >= self.settings.LLM_RETRY_COUNT:
                    raise
                time.sleep(min(2**attempt, 8))
        else:
            raise RuntimeError("LLM request failed without an exception") from last_error

        if not isinstance(parsed, dict):
            raise ValueError("LLM response did not contain a JSON object")
        return parsed

    def _build_payload(
        self, endpoint: str, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        normalized_endpoint = endpoint.lower()

        if normalized_endpoint.endswith("/api/generate"):
            if not self.settings.LLM_MODEL:
                raise ValueError(
                    "LLM_MODEL must be configured when using an Ollama /api/generate endpoint."
                )
            return {
                "model": self.settings.LLM_MODEL,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "format": "json",
                "stream": False,
                "options": self._ollama_options(),
            }

        if normalized_endpoint.endswith("/api/chat"):
            if not self.settings.LLM_MODEL:
                raise ValueError(
                    "LLM_MODEL must be configured when using an Ollama /api/chat endpoint."
                )
            return {
                "model": self.settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "format": "json",
                "stream": False,
                "options": self._ollama_options(),
            }

        if not self.settings.LLM_MODEL:
            raise ValueError(
                "LLM_MODEL must be configured for OpenAI-compatible chat completion endpoints."
            )

        return {
            "model": self.settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

    def _ollama_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": 0.1}
        if self.settings.LLM_NUM_CTX:
            options["num_ctx"] = self.settings.LLM_NUM_CTX
        return options

    @staticmethod
    def _extract_content(response_json: dict[str, Any]) -> Any:
        if "response" in response_json:
            return response_json["response"]

        if "message" in response_json and isinstance(response_json["message"], dict):
            return response_json["message"].get("content", "")

        if "choices" in response_json:
            choice = response_json["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                return "".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict)
                )
            return content

        raise ValueError("Unsupported LLM response shape")

    @staticmethod
    def _extract_json(content: Any) -> Any:
        if isinstance(content, dict):
            return content

        text = str(content).strip()
        code_block_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if code_block_match:
            text = code_block_match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            object_start = text.find("{")
            object_end = text.rfind("}")
            if object_start >= 0 and object_end > object_start:
                return json.loads(text[object_start : object_end + 1])
            raise


class ManifestAnalysis:
    SYSTEM_PROMPT = (
        "You analyze collaborative documentation inventories before RAG ingestion. "
        "Identify only high-confidence series relationships such as monthly sequences, "
        "version chains, multi-part internal technical reports, or evolutionary design notes. "
        "Return strict JSON."
    )

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def analyze_directory(
        self, directory: str | Path, files: Iterable[str | Path], source_root: str | Path
    ) -> ManifestResult:
        directory_path = Path(directory).expanduser().resolve()
        source_root_path = Path(source_root).expanduser().resolve()

        manifest_rows: list[dict[str, Any]] = []
        sorted_files = sorted(
            [Path(file_path).expanduser().resolve() for file_path in files],
            key=lambda item: (item.stat().st_mtime, item.name.lower()),
        )
        if len(sorted_files) > self.llm_client.settings.MANIFEST_MAX_FILES:
            selected_files = [
                *sorted_files[: self.llm_client.settings.MANIFEST_MAX_FILES // 2],
                *sorted_files[-(self.llm_client.settings.MANIFEST_MAX_FILES // 2) :],
            ]
        else:
            selected_files = sorted_files

        for path in selected_files:
            stat = path.stat()
            manifest_rows.append(
                {
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "created_epoch": round(stat.st_ctime, 2),
                    "modified_epoch": round(stat.st_mtime, 2),
                }
            )

        user_prompt = json.dumps(
            {
                "directory": str(directory_path.relative_to(source_root_path)),
                "total_file_count": len(sorted_files),
                "manifest_file_count": len(selected_files),
                "manifest": sorted(
                    manifest_rows,
                    key=lambda item: (item["modified_epoch"], item["name"]),
                ),
                "response_schema": {
                    "series_files": ["file names only"],
                    "series_groups": [
                        {
                            "name": "series label",
                            "files": ["file names only"],
                            "signal": "why the sequence looks related",
                        }
                    ],
                    "high_value_candidates": ["file names only"],
                    "reasoning": "short explanation",
                },
            },
            ensure_ascii=False,
            indent=2,
        )

        payload = self.llm_client.complete_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        return self._validate_manifest(payload)

    @staticmethod
    def _validate_manifest(payload: dict[str, Any]) -> ManifestResult:
        normalized = {
            "series_files": _coerce_string_list(payload.get("series_files")),
            "series_groups": [],
            "high_value_candidates": _coerce_string_list(
                payload.get("high_value_candidates")
            ),
            "reasoning": str(payload.get("reasoning", "")),
        }

        raw_groups = payload.get("series_groups", [])
        if isinstance(raw_groups, dict):
            raw_groups = [raw_groups]
        if isinstance(raw_groups, list):
            for group in raw_groups:
                if not isinstance(group, dict):
                    continue
                normalized["series_groups"].append(
                    {
                        "name": str(group.get("name", "")),
                        "files": _coerce_string_list(group.get("files")),
                        "signal": str(group.get("signal", "")),
                    }
                )

        try:
            return ManifestResult.model_validate(normalized)
        except ValidationError:
            return ManifestResult()


class SemanticScoring:
    SYSTEM_PROMPT = (
        "You score and classify enterprise technical documents for pre-RAG triage. "
        "Prioritize reusable engineering value, evidence-backed implementation detail, and safe downstream use. "
        "Use these categories only: Architecture, Design, Implementation, Operations, CaseStudy, Research, Business, Thinking, Series, LowQuality. "
        "Do not reward confidential names by themselves; reward reusable patterns after abstraction. "
        "Prefer precise, short reasoning and return strict JSON."
    )

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def score_document(
        self,
        file_path: str | Path,
        clean_markdown: str,
        profile: DocumentProfile,
        manifest: ManifestResult,
        output_language: str | None = None,
    ) -> SemanticScore:
        path = Path(file_path).expanduser().resolve()
        language_policy = build_output_language_policy(
            output_language or self.llm_client.settings.OUTPUT_LANGUAGE,
            clean_markdown,
        )
        prompt_body = json.dumps(
            {
                "document_name": path.name,
                "document_role_context": [
                    "Collaborative Documentation",
                    "Internal Technical Reports",
                    "Evolutionary Design",
                    "Incident Reviews",
                    "Research Notes",
                    "Business and Operations Analyses",
                ],
                "manifest_hints": manifest.model_dump(),
                "meta_features": profile.to_llm_payload(),
                "local_signals": self._infer_local_signals(path.name, clean_markdown),
                "output_language": language_policy,
                "samples": self._build_samples(clean_markdown),
                "classification_schema": {
                    "document_kind_options": [
                        "ArchitectureDecision",
                        "ImplementationGuide",
                        "IncidentReview",
                        "ResearchReport",
                        "ExperienceSummary",
                        "Tutorial",
                        "BusinessAnalysis",
                        "MeetingNotes",
                        "Reference",
                        "Unknown",
                    ],
                    "topic_tag_examples": [
                        "AIEngineering",
                        "Agent",
                        "RAG",
                        "LLM",
                        "KnowledgeGraph",
                        "Search",
                        "Recommendation",
                        "Data",
                        "DistributedSystems",
                        "Middleware",
                        "Storage",
                        "Database",
                        "Stability",
                        "Observability",
                        "Performance",
                        "Frontend",
                        "Security",
                        "Business",
                        "Product",
                        "Testing",
                        "EngineeringProductivity",
                        "Governance",
                    ],
                },
                "scoring_dimensions": [
                    "Knowledge Density",
                    "Implementation Specificity",
                    "Logical Structure",
                    "Evidence Richness",
                    "Actionability",
                    "Strategic Value",
                    "Freshness",
                    "Uniqueness",
                    "Sensitivity Risk",
                    "Public Writing Suitability",
                ],
                "summary_requirements": [
                    "Write summary and reason in output_language.resolved_language.",
                    "Use 3-6 compact sentences; keep a comparable length to 180-450 Chinese characters.",
                    "Keep category, document_kind, and topic_tags as stable schema/canonical values rather than translating enum names.",
                    "Capture the domain/problem, concrete approach or mechanism, key evidence/result, and reusable takeaway.",
                    "Do not copy navigation chrome, page markers, author/date/view-count text, copyright boilerplate, or table-of-contents fragments.",
                    "Avoid generic praise such as 'this document is valuable'; summarize the actual knowledge.",
                    "When public reuse is risky, abstract company/customer/system names while keeping the transferable pattern.",
                ],
                "response_schema": {
                    "quality": "0-100 integer",
                    "category": "Architecture|Design|Implementation|Operations|CaseStudy|Research|Business|Thinking|Series|LowQuality",
                    "document_kind": "one of classification_schema.document_kind_options",
                    "topic_tags": "0-8 short canonical tags; prefer topic_tag_examples where applicable",
                    "summary": "high-signal 3-6 sentence knowledge summary following summary_requirements",
                    "knowledge_density": "0-100 integer",
                    "implementation_specificity": "0-100 integer",
                    "logical_structure": "0-100 integer",
                    "evidence_richness": "0-100 integer; concrete data, examples, diagrams, incidents, or citations",
                    "actionability": "0-100 integer; how directly the document can guide engineering decisions",
                    "strategic_value": "0-100 integer; long-term value for architecture, platform, governance, or business judgement",
                    "freshness": "0-100 integer; likely current usefulness based on content and metadata",
                    "uniqueness": "0-100 integer; penalize generic tutorials, duplicates, and copied public content",
                    "sensitivity_risk": "0-100 integer; higher means more likely to contain confidential, internal, customer, security, or operational details",
                    "public_writing_suitability": "0-100 integer; higher means safer to use for public abstracted writing without leaking specifics",
                    "reason": "short explanation",
                },
            },
            ensure_ascii=False,
            indent=2,
        )

        payload = self.llm_client.complete_json(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=prompt_body,
        )
        return self._validate_score(payload)

    @staticmethod
    def _build_samples(clean_markdown: str) -> dict[str, str]:
        normalized = _strip_invalid_surrogates(clean_markdown.strip())
        first_chunk = normalized[:1000]

        if len(normalized) <= 500:
            middle_chunk = normalized
        else:
            midpoint = len(normalized) // 2
            start = max(0, midpoint - 250)
            middle_chunk = normalized[start : start + 500]

        return {
            "first_1000_chars": first_chunk,
            "middle_500_chars": middle_chunk,
        }

    @staticmethod
    def _infer_local_signals(file_name: str, clean_markdown: str) -> list[str]:
        haystack = f"{file_name}\n{clean_markdown[:3000]}".lower()
        patterns = {
            "architecture": r"架构|architecture|architectural|系统设计|技术方案",
            "implementation": r"实现|源码|原理|代码|implementation|source|code",
            "operations": r"稳定性|故障|排障|运维|容灾|高可用|监控|sre|incident|oncall|observability",
            "case_study": r"复盘|案例|case\s*study|问题定位|问题排查|故障分析",
            "research": r"研报|调研|论文|paper|survey|benchmark|report",
            "business": r"业务|产品|增长|商业|交易|支付|风控|营销|运营|business|product",
            "ai_engineering": r"\bai\b|大模型|llm|agent|rag|prompt|embedding|向量|知识库|智能体",
            "search_or_recommendation": r"搜索|推荐|排序|召回|检索|search|recommendation|ranking",
            "frontend": r"前端|浏览器|客户端|\bweb\b|react|vue|weex|渲染",
            "data_or_storage": r"数据|数据库|存储|sql|redis|tair|mysql|clickhouse|kafka|storage",
            "security": r"安全|风控|黑产|攻击|漏洞|权限|隐私|security|risk",
        }
        signals = [
            name for name, pattern in patterns.items() if re.search(pattern, haystack)
        ]
        return signals[:12]

    @staticmethod
    def _validate_score(payload: dict[str, Any]) -> SemanticScore:
        try:
            return SemanticScore.model_validate(payload)
        except ValidationError:
            normalized = {
                "quality": _coerce_score(payload.get("quality", payload.get("score", 0))),
                "category": _normalize_category(
                    payload.get("category", payload.get("type", "LowQuality"))
                ),
                "document_kind": _normalize_document_kind(
                    payload.get("document_kind", "Unknown")
                ),
                "topic_tags": _normalize_topic_tags(payload.get("topic_tags")),
                "summary": _normalize_summary(payload.get("summary")),
                "knowledge_density": _coerce_score(payload.get("knowledge_density", 0)),
                "implementation_specificity": _coerce_score(
                    payload.get("implementation_specificity", 0)
                ),
                "logical_structure": _coerce_score(payload.get("logical_structure", 0)),
                "evidence_richness": _coerce_score(payload.get("evidence_richness", 0)),
                "actionability": _coerce_score(payload.get("actionability", 0)),
                "strategic_value": _coerce_score(payload.get("strategic_value", 0)),
                "freshness": _coerce_score(payload.get("freshness", 0)),
                "uniqueness": _coerce_score(payload.get("uniqueness", 0)),
                "sensitivity_risk": _coerce_score(payload.get("sensitivity_risk", 0)),
                "public_writing_suitability": _coerce_score(
                    payload.get("public_writing_suitability", 0)
                ),
                "reason": payload.get("reason", payload.get("rationale", "")),
            }
            return SemanticScore.model_validate(normalized)


LANGUAGE_LABELS = {
    "zh-CN": "Simplified Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
}


def build_output_language_policy(
    requested_language: str | None, clean_markdown: str
) -> dict[str, str]:
    requested = str(requested_language or "auto").strip() or "auto"
    detected = infer_primary_language(clean_markdown)
    resolved = detected if requested == "auto" else requested
    return {
        "requested": requested,
        "detected_primary_language": detected,
        "resolved_language": resolved,
        "resolved_language_name": LANGUAGE_LABELS.get(resolved, resolved),
        "instruction": (
            "Infer from the document body and use the detected primary language."
            if requested == "auto"
            else f"Use {LANGUAGE_LABELS.get(resolved, resolved)} regardless of input language."
        ),
    }


def infer_primary_language(text: str) -> str:
    sample = _strip_invalid_surrogates(text[:8000])
    counts = {
        "zh-CN": len(re.findall(r"[\u4e00-\u9fff]", sample)),
        "ja": len(re.findall(r"[\u3040-\u30ff]", sample)),
        "ko": len(re.findall(r"[\uac00-\ud7af]", sample)),
    }
    latin_words = re.findall(r"[A-Za-zÀ-ÿ]+", sample)
    latin_count = sum(len(word) for word in latin_words)
    total_signal = latin_count + sum(counts.values())
    if total_signal == 0:
        return "en"
    if counts["ja"] >= 20 and counts["ja"] >= counts["zh-CN"] * 0.15:
        return "ja"
    if counts["ko"] >= 20:
        return "ko"
    if counts["zh-CN"] >= 20 and counts["zh-CN"] >= latin_count * 0.25:
        return "zh-CN"
    if latin_count > 0:
        return infer_latin_language(" ".join(latin_words[:1200]))
    return max(counts, key=counts.get)


def infer_latin_language(text: str) -> str:
    lowered = f" {text.lower()} "
    hints = {
        "de": (" der ", " die ", " und ", " nicht ", " mit ", " für ", " das ", " ist "),
        "fr": (" le ", " la ", " les ", " des ", " une ", " pour ", " avec ", " dans "),
        "es": (" el ", " la ", " los ", " una ", " para ", " con ", " que ", " del "),
    }
    scores = {
        language: sum(lowered.count(token) for token in tokens)
        for language, tokens in hints.items()
    }
    best_language = max(scores, key=scores.get)
    return best_language if scores[best_language] >= 4 else "en"


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return []


def _normalize_summary(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        text = " ".join(str(item) for item in value if item is not None)
    else:
        text = str(value)
    text = _strip_invalid_surrogates(text)
    text = re.sub(r"<!--.*?-->", " ", text)
    text = re.sub(r"[\ue000-\uf8ff]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:800].rstrip()


def _coerce_score(value: Any) -> int:
    try:
        score = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0
    return min(100, max(0, score))


def _normalize_document_kind(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Unknown"

    normalized = re.sub(r"[\s_-]+", "", text).lower()
    aliases = {
        "architecturedecision": "ArchitectureDecision",
        "architecture": "ArchitectureDecision",
        "technicalproposal": "ArchitectureDecision",
        "方案": "ArchitectureDecision",
        "架构": "ArchitectureDecision",
        "implementationguide": "ImplementationGuide",
        "implementation": "ImplementationGuide",
        "guide": "ImplementationGuide",
        "教程": "Tutorial",
        "指南": "ImplementationGuide",
        "incidentreview": "IncidentReview",
        "incident": "IncidentReview",
        "postmortem": "IncidentReview",
        "case": "IncidentReview",
        "复盘": "IncidentReview",
        "故障": "IncidentReview",
        "researchreport": "ResearchReport",
        "research": "ResearchReport",
        "report": "ResearchReport",
        "研报": "ResearchReport",
        "experience": "ExperienceSummary",
        "experiencesummary": "ExperienceSummary",
        "summary": "ExperienceSummary",
        "总结": "ExperienceSummary",
        "tutorial": "Tutorial",
        "businessanalysis": "BusinessAnalysis",
        "business": "BusinessAnalysis",
        "业务": "BusinessAnalysis",
        "meetingnotes": "MeetingNotes",
        "meeting": "MeetingNotes",
        "会议": "MeetingNotes",
        "reference": "Reference",
        "manual": "Reference",
        "手册": "Reference",
        "unknown": "Unknown",
    }
    return aliases.get(normalized, text if text in set(aliases.values()) else "Unknown")


def _normalize_topic_tags(value: Any) -> list[str]:
    raw_values = _coerce_string_list(value)
    aliases = {
        "ai": "AIEngineering",
        "aiengineering": "AIEngineering",
        "大模型": "LLM",
        "llm": "LLM",
        "agent": "Agent",
        "智能体": "Agent",
        "rag": "RAG",
        "知识库": "KnowledgeGraph",
        "knowledgegraph": "KnowledgeGraph",
        "graph": "KnowledgeGraph",
        "图谱": "KnowledgeGraph",
        "search": "Search",
        "搜索": "Search",
        "recommendation": "Recommendation",
        "推荐": "Recommendation",
        "data": "Data",
        "数据": "Data",
        "distributed": "DistributedSystems",
        "distributedsystems": "DistributedSystems",
        "分布式": "DistributedSystems",
        "middleware": "Middleware",
        "中间件": "Middleware",
        "storage": "Storage",
        "存储": "Storage",
        "database": "Database",
        "数据库": "Database",
        "stability": "Stability",
        "稳定性": "Stability",
        "observability": "Observability",
        "可观测性": "Observability",
        "performance": "Performance",
        "性能": "Performance",
        "frontend": "Frontend",
        "前端": "Frontend",
        "security": "Security",
        "安全": "Security",
        "business": "Business",
        "业务": "Business",
        "product": "Product",
        "产品": "Product",
        "testing": "Testing",
        "测试": "Testing",
        "engineeringproductivity": "EngineeringProductivity",
        "效能": "EngineeringProductivity",
        "governance": "Governance",
        "治理": "Governance",
    }

    normalized_tags: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        compact = re.sub(r"[\s_-]+", "", raw.strip())
        if not compact:
            continue
        tag = aliases.get(compact.lower(), re.sub(r"[^0-9A-Za-z\u4e00-\u9fff#+.]", "", raw.strip()))
        if not tag or len(tag) > 40:
            continue
        if tag not in seen:
            normalized_tags.append(tag)
            seen.add(tag)
        if len(normalized_tags) >= 8:
            break
    return normalized_tags


def _normalize_category(value: Any) -> str:
    text = str(value).strip()
    allowed = {
        "Architecture",
        "Design",
        "Implementation",
        "Operations",
        "CaseStudy",
        "Research",
        "Business",
        "Thinking",
        "Series",
        "LowQuality",
    }
    if text in allowed:
        return text

    normalized = text.lower()
    aliases = {
        "architecture": "Architecture",
        "architectural": "Architecture",
        "架构": "Architecture",
        "design": "Design",
        "设计": "Design",
        "implementation": "Implementation",
        "implement": "Implementation",
        "code": "Implementation",
        "工程": "Implementation",
        "实现": "Implementation",
        "operations": "Operations",
        "ops": "Operations",
        "sre": "Operations",
        "stability": "Operations",
        "运维": "Operations",
        "稳定性": "Operations",
        "排障": "Operations",
        "故障": "Operations",
        "casestudy": "CaseStudy",
        "case_study": "CaseStudy",
        "case study": "CaseStudy",
        "案例": "CaseStudy",
        "复盘": "CaseStudy",
        "research": "Research",
        "paper": "Research",
        "report": "Research",
        "研报": "Research",
        "研究": "Research",
        "business": "Business",
        "product": "Business",
        "业务": "Business",
        "产品": "Business",
        "商业": "Business",
        "thinking": "Thinking",
        "thought": "Thinking",
        "思考": "Thinking",
        "series": "Series",
        "sequence": "Series",
        "系列": "Series",
        "lowquality": "LowQuality",
        "low_quality": "LowQuality",
        "low quality": "LowQuality",
        "低质量": "LowQuality",
    }
    return aliases.get(normalized, "LowQuality")


def _strip_invalid_surrogates(value: str) -> str:
    return value.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
