import json
from sqlalchemy.orm import sessionmaker

from webapp.api.db import engine
from agent.report_generator import generate_report

# Use project 1 for testing (from logs)
project_id = 1

Session = sessionmaker(bind=engine)
db = Session()

try:
    print(f"Generating HTML report for project {project_id}...")
    artifacts = generate_report(db, project_id, formats=["html"])
    
    if artifacts.html_bytes:
        print(f"SUCCESS: Generated {len(artifacts.html_bytes)} bytes of HTML.")
        # Save a snippet to check
        with open("test_report.html", "wb") as f:
            f.write(artifacts.html_bytes)
        print("Report saved to test_report.html")
    else:
        print("FAILED: No HTML bytes returned.")

except Exception as e:
    print(f"ERROR: {e}")
finally:
    db.close()
