from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT = Path("output/pdf/subscription_analysis_demo.pdf")


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Subscription Analysis Demo Brief",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SmallBody",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#17324d"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )

    story = [
        Paragraph("Subscription Analysis Demo Brief", styles["Title"]),
        Paragraph(
            "This demo PDF is designed to test PDF extraction, RAG ingestion, SQL comparison, "
            "source citation, and multi-agent tool routing for the Enterprise AI Chatbot.",
            styles["SmallBody"],
        ),
        Spacer(1, 8),
        Paragraph("Operational Definitions", styles["Section"]),
        Paragraph(
            "Active subscriptions are transactions where Status is Active. Renewal risk includes "
            "subscriptions that are expired, inactive, or ending within 30 days. Payment leakage "
            "means payment gateway rows where Status is not Success. SLA breach means the time "
            "between CreatedDate and ResolvedDate exceeds SLA_Hours; open tickets should be "
            "measured against the current time.",
            styles["SmallBody"],
        ),
        Paragraph("Recommended SQL Tables", styles["Section"]),
    ]

    table_data = [
        ["Business Area", "Table", "Key Columns"],
        ["Society profile", "Society_Master_Data", "SocietyID, SocietyName, City, State, TotalFlats"],
        ["Plans", "Subscription_Plans", "PlanID, PlanName, DurationMonths, Price, Features"],
        ["Lifecycle", "Subscription_Transactions", "SubscriptionID, SocietyID, PlanID, StartDate, EndDate, Status"],
        ["Payments", "Payment_Gateway", "PaymentID, SocietyID, Amount, PaymentMethod, Status, PaymentDate"],
        ["Support", "Complaint_tickets", "TicketID, SocietyID, Category, SLA_Hours, Status"],
    ]
    table = Table(table_data, colWidths=[1.3 * inch, 1.75 * inch, 3.45 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d2dc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fb")]),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend(
        [
            table,
            Paragraph("Executive Test Scenarios", styles["Section"]),
            Paragraph(
                "1. Ask the chatbot to summarize this PDF. The PDF tool should extract the business definitions. "
                "2. Ingest this PDF into RAG and ask for payment leakage or SLA breach definitions. "
                "3. Ask a multi-tool question that compares renewal risk guidance from this PDF with SQL rows "
                "from Subscription_Transactions.",
                styles["SmallBody"],
            ),
            Paragraph("Expected Analytical Outputs", styles["Section"]),
            Paragraph(
                "A production-grade answer should cite the PDF or indexed knowledge source, show the SQL query "
                "used for Subscription_Analysis, identify failed payments, active contract value by plan, "
                "near-expiring subscriptions, and SLA-breached complaint tickets.",
                styles["SmallBody"],
            ),
            Paragraph("Governance Notes", styles["Section"]),
            Paragraph(
                "SQL access for this chatbot should remain read-only. Destructive statements such as INSERT, "
                "UPDATE, DELETE, DROP, ALTER, TRUNCATE, MERGE, EXEC, GRANT, and REVOKE must be blocked. "
                "Answers should mention uncertainty when database rows or document evidence are missing.",
                styles["SmallBody"],
            ),
        ]
    )
    doc.build(story)


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT)

