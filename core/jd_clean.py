"""
Strips generic company boilerplate (About Us, EEO statements, benefits/perks
blurbs, culture pitches) from job descriptions before they're sent to the LLM.

These sections are near-identical across every posting from the same company
and carry no job-specific signal for fit scoring or ATS optimization — cutting
them frees character budget for the parts that actually matter: responsibilities
and qualifications.
"""

import re

# Matches a boilerplate section heading on its own line (the common case for
# ATS-templated postings — Greenhouse, Lever, Workday, etc. — which usually
# render these as clearly separated headed sections, not inline prose).
_BOILERPLATE_HEADING = re.compile(
    r"""
    ^[ \t]*
    (
        about\s+(the\s+)?(company|us|team|organi[sz]ation|our\s+\w+)
      | who\s+we\s+are
      | our\s+culture
      | why\s+(join|work\s+(at|for|with))\s+\w*
      | equal\s+(employment\s+)?opportunity(\s+employer)?
      | eeo(\s*/\s*aa)?\s*statement
      | diversity(\s*,?\s*equity)?(\s+and\s+inclusion)?
      | compliance\s+language
      | benefits?(\s*(and|&)\s*perks?)?
      | perks?(\s*(and|&)\s*benefits?)?
      | what\s+we\s+offer
      | our\s+benefits
      | applicant\s+privacy\s+notice
      | accommodations?\s+statement
      | reasonable\s+accommodation
    )
    [ \t]*:?[ \t]*$
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# Matches "About <Company Name>" as its own heading line (e.g. "About Acme
# Corp", "About Stripe, Inc") — excludes "About this role/the role/our role",
# which usually introduces actual job-scope content, not company boilerplate.
_ABOUT_COMPANY_HEADING = re.compile(
    r"""^[ \t]*about\s+
    (?!this\b|the\s+role\b|your\b|our\s+role\b)
    [A-Z][\w&.,'-]*(\s+[A-Z][\w&.,'-]*){0,4}
    [ \t]*:?[ \t]*$""",
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)


def strip_boilerplate(text: str) -> str:
    """
    Cut everything from the first recognized boilerplate heading onward.
    Conservative: only trims on a clear heading match on its own line, never
    mid-paragraph — a miss just means boilerplate stays in (harmless, just
    uses more of the character budget), never cuts real content.
    """
    if not text:
        return text
    positions = [
        m.start()
        for m in (_BOILERPLATE_HEADING.search(text), _ABOUT_COMPANY_HEADING.search(text))
        if m
    ]
    if positions:
        return text[: min(positions)].rstrip()
    return text
