from pathlib import Path
from validation.code_audit.engine import CodeAuditEngine
from validation.code_audit.reporter import AuditReporter

def main():
    engine = CodeAuditEngine()
    report = engine.audit_directory(Path("knowledge"))

    reporter = AuditReporter()
    print(reporter.to_markdown(report))

    Path("reports").mkdir(exist_ok=True)
    reporter.save(report, Path("reports/code_audit.md"))
    print("\n✅ Raport zapisany do reports/code_audit.md")

if __name__ == "__main__":
    main()