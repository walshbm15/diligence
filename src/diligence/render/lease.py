"""Commercial lease — text-heavy legal document with the clauses the
pipeline must find: term, rent, rent review, break clause, 1954 Act status."""

from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer

from diligence.dataroom.spec import CompanyInfo, LeaseData
from diligence.render.common import BASE, CLAUSE, H2, SMALL, TITLE, doc_template, ukdate


def render_lease(company: CompanyInfo, data: LeaseData, path: str) -> None:
    doc = doc_template(path)
    end_date = data.start.replace(year=data.start.year + data.term_years)
    rent = f"£{data.annual_rent // 100:,}"

    clauses: list[tuple[str, str]] = [
        ("1. DEFINITIONS AND INTERPRETATION",
         f'"Landlord" means {data.landlord}. "Tenant" means {data.tenant} '
         f'(company number {companyno(company)}). "Premises" means the ground '
         f"floor lock-up shop and ancillary accommodation known as "
         f"{data.premises}, shown edged red on the attached plan. "
         f'"Term" means the term of years granted by this lease.'),
        ("2. DEMISE AND TERM",
         f"The Landlord lets the Premises to the Tenant for a term of "
         f"{data.term_years} years commencing on and including "
         f"{ukdate(data.start)} and ending on {ukdate(end_date)}, subject to "
         f"the provisions for earlier determination contained in this lease."),
        ("3. RENT",
         f"The Tenant shall pay to the Landlord without deduction or set-off "
         f"a yearly rent of {rent} ({words_pounds(data.annual_rent)}) per "
         f"annum, payable by equal monthly instalments in advance on the "
         f"first day of each month, the first payment to be made on the "
         f"Term commencement date."),
        ("4. RENT REVIEW",
         f"The yearly rent shall be reviewed on {ukdate(data.rent_review_date)} "
         f"(the “Review Date”) to the open market rent of the Premises at the "
         f"Review Date, such review to be upwards only. If the revised rent "
         f"has not been agreed by the Review Date the matter shall be "
         f"referred to an independent surveyor acting as expert."),
        ("5. REPAIR AND DECORATION",
         "The Tenant shall keep the Premises in good and substantial repair "
         "and condition (fair wear and tear excepted in respect of the "
         "external structure) and shall redecorate the interior in the last "
         "year of the Term. On the expiry or sooner determination of the "
         "Term the Tenant shall yield up the Premises in the state of repair "
         "required by this lease, and shall pay the proper cost of any "
         "schedule of dilapidations served by the Landlord."),
        ("6. USE",
         "Not to use the Premises otherwise than as a café / coffee shop "
         "with ancillary retail sale of food and beverages within Class E "
         "of the Town and Country Planning (Use Classes) Order 1987, nor to "
         "permit the sale of hot food for consumption off the Premises "
         "after 9.00 pm."),
        ("7. ALIENATION",
         "The Tenant shall not assign, underlet, charge or part with "
         "possession of the whole or any part of the Premises without the "
         "prior written consent of the Landlord, such consent not to be "
         "unreasonably withheld. Any permitted assignment shall require an "
         "authorised guarantee agreement."),
    ]

    if data.break_date:
        clauses.append((
            "8. TENANT'S AND LANDLORD'S OPTION TO DETERMINE (BREAK CLAUSE)",
            f"Either party may determine this lease on {ukdate(data.break_date)} "
            f"(the “Break Date”) by serving on the other not less than "
            f"{data.break_notice_months} months' prior written notice. "
            f"A notice served by the Tenant shall be of no effect unless the "
            f"yearly rent has been paid up to the Break Date and vacant "
            f"possession of the Premises is given on the Break Date. On "
            f"determination pursuant to this clause the Term shall cease "
            f"absolutely but without prejudice to accrued rights."))

    act_clause_no = "9" if data.break_date else "8"
    if data.inside_lta_1954:
        act_text = ("This lease is granted WITH the benefit of the security of "
                    "tenure provisions of Part II of the Landlord and Tenant "
                    "Act 1954. Sections 24 to 28 of that Act are not excluded.")
    else:
        act_text = ("Having been authorised by the court, the parties agree "
                    "that the provisions of sections 24 to 28 of the Landlord "
                    "and Tenant Act 1954 are EXCLUDED in relation to the "
                    "tenancy created by this lease.")
    clauses.append((f"{act_clause_no}. LANDLORD AND TENANT ACT 1954", act_text))

    story = [
        Spacer(0, 30 * mm),
        Paragraph(f"DATED {ukdate(data.start)}", BASE),
        Spacer(0, 10 * mm),
        Paragraph("LEASE", TITLE),
        Paragraph("of premises known as", BASE),
        Paragraph(data.premises, H2),
        Spacer(0, 10 * mm),
        Paragraph("between", BASE),
        Paragraph(f"{data.landlord} (1)", H2),
        Paragraph("and", BASE),
        Paragraph(f"{data.tenant} (2)", H2),
        PageBreak(),
    ]
    for heading, body in clauses:
        story.append(Paragraph(heading, H2))
        story.append(Paragraph(body, CLAUSE))
    story += [
        Spacer(0, 8 * mm),
        Paragraph("EXECUTED as a deed by the parties on the date first above "
                  "written.", CLAUSE),
        Spacer(0, 12 * mm),
        Paragraph(f"Signed for and on behalf of {data.landlord}", SMALL),
        Spacer(0, 8 * mm),
        Paragraph(f"Signed for and on behalf of {data.tenant} "
                  f"(Margaret Holt, Director)", SMALL),
    ]
    doc.build(story)


def companyno(company: CompanyInfo) -> str:
    return company.number


def words_pounds(pence: int) -> str:
    """£26,000 -> 'twenty-six thousand pounds' (limited vocabulary)."""
    thousands = pence // 100 // 1000
    units = {
        20: "twenty", 21: "twenty-one", 22: "twenty-two", 23: "twenty-three",
        24: "twenty-four", 25: "twenty-five", 26: "twenty-six",
        27: "twenty-seven", 28: "twenty-eight", 29: "twenty-nine",
        30: "thirty", 31: "thirty-one", 32: "thirty-two",
    }
    word = units.get(thousands)
    return f"{word} thousand pounds" if word else f"£{pence // 100:,}"
