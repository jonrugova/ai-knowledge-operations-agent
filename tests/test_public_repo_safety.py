import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", path],
        cwd=ROOT,
        check=False,
    )
    return result.returncode == 0


class PublicRepositorySafetyTests(unittest.TestCase):
    def test_gitignore_exists_and_protects_local_artifacts(self):
        gitignore = ROOT / ".gitignore"
        self.assertTrue(gitignore.is_file())
        for path in (
            ".env",
            "data/approvals.json",
            "data/executions.json",
            "data/traces.jsonl",
            "documents/private-policy.docx",
            "documents/extracted_text.txt",
            "documents/chunks.json",
            "screenshots/review.jpg",
            "frontend/node_modules/package.json",
            "frontend/dist/index.html",
            ".agents/memory/MEMORY.md",
            "attached_assets/private-note.txt",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_ignored(path))

    def test_public_keep_files_are_not_ignored(self):
        self.assertFalse(is_ignored("data/.gitkeep"))
        self.assertFalse(is_ignored("documents/.gitkeep"))
        self.assertFalse(is_ignored("examples/sample_knowledge.txt"))

    def test_sample_knowledge_is_explicitly_fictional(self):
        sample = (
            ROOT / "examples" / "sample_knowledge.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("SAMPLE / FICTIONAL DATA", sample)
        self.assertIn("Northstar Atelier", sample)
        self.assertNotIn("PRIVATE_COMPANY_NAME_A", sample)
        self.assertNotIn("PRIVATE_COMPANY_NAME_B", sample)

    def test_public_docs_are_not_private_company_specific(self):
        for relative_path in (
            "SECURITY.md",
            "PUBLIC_REPO_CHECKLIST.md",
            ".env.example",
        ):
            content = (ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertNotIn("PRIVATE_COMPANY_NAME_A", content)
                self.assertNotIn("PRIVATE_COMPANY_NAME_B", content)
                self.assertNotRegex(content, r"sk-[A-Za-z0-9_-]{20,}")

    def test_public_source_has_no_known_private_company_names(self):
        candidate_paths = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and "node_modules" not in path.parts
            and ".pythonlibs" not in path.parts
            and ".local" not in path.parts
            and ".agents" not in path.parts
            and "attached_assets" not in path.parts
            and "documents" not in path.parts
            and "data" not in path.parts
            and "screenshots" not in path.parts
            and "evaluations/private" not in str(path)
            and path.name != "test_public_repo_safety.py"
            and path.suffix
            in {".py", ".md", ".txt", ".json", ".tsx", ".ts", ".css"}
        ]
        private_names = re.compile(
            r"PRIVATE_COMPANY_NAME_A|PRIVATE_COMPANY_NAME_B",
            re.IGNORECASE,
        )
        for path in candidate_paths:
            with self.subTest(path=path.relative_to(ROOT)):
                content = path.read_text(encoding="utf-8", errors="ignore")
                self.assertIsNone(private_names.search(content))

    def test_dockerfile_is_present_and_hardened(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM node:22-bookworm-slim AS frontend-builder", dockerfile)
        self.assertIn("npm ci", dockerfile)
        self.assertIn("FROM python:3.12-slim AS runtime", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("USER appuser", dockerfile)
        self.assertNotRegex(
            dockerfile,
            r"(?im)^\s*ARG\s+(OPENAI_API_KEY|DATABASE_URL|SESSION_SECRET|ADMIN_PASSWORD|EMPLOYEE_PASSWORD)\b",
        )
        self.assertNotIn("USER root", dockerfile)
        self.assertNotIn("COPY . ", dockerfile)

    def test_dockerignore_protects_private_build_inputs(self):
        dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        for pattern in (
            ".git",
            ".env",
            "data/approvals.json",
            "data/executions.json",
            "data/traces.jsonl",
            "documents/*.docx",
            "documents/extracted*",
            "documents/chunks.json",
            "evaluations/private/",
            "screenshots/",
            "attached_assets/",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, dockerignore)
        self.assertNotIn("examples/sample_knowledge.txt", dockerignore)

    def test_compose_uses_runtime_secrets_and_private_network_database(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("pgvector/pgvector:pg16", compose)
        self.assertIn("knowledge_demo_db:", compose)
        self.assertIn("condition: service_healthy", compose)
        self.assertIn("OPENAI_API_KEY: ${OPENAI_API_KEY:", compose)
        self.assertIn("SESSION_SECRET: ${SESSION_SECRET:", compose)
        self.assertIn("ADMIN_PASSWORD: ${ADMIN_PASSWORD:", compose)
        self.assertIn("EMPLOYEE_PASSWORD: ${EMPLOYEE_PASSWORD:", compose)
        self.assertNotIn("5432:5432", compose)
        self.assertNotRegex(
            compose,
            r"(?i)(sk-[A-Za-z0-9_-]{20,}|postgres(ql)?://[^$\s]+)",
        )


if __name__ == "__main__":
    unittest.main()