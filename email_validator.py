
import dns.resolver
import re
import smtplib
import socket

def _mx_host_resolves(hostname: str) -> bool:
    """Check if an MX hostname has a valid A or AAAA record."""
    for rdtype in ("A", "AAAA"):
        try:
            answers = dns.resolver.resolve(hostname, rdtype, lifetime=5)
            if len(answers) > 0:
                return True
        except Exception:
            continue
    return False


def validate_email(email: str) -> dict:
    """
    Validate email via regex, MX record check, and MX host resolution.
    Returns: {"valid": bool, "mx": str|None, "error": str|None}
    """
    if not email or "@" not in email:
        return {"valid": False, "mx": None, "error": "Invalid format"}

    domain = email.split("@")[1]

    # 1. DNS MX Record Check
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_records = sorted(mx_records, key=lambda r: r.preference)
        primary_mx = str(mx_records[0].exchange)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return {"valid": False, "mx": None, "error": "Domain has no MX records"}
    except Exception as e:
        return {"valid": False, "mx": None, "error": str(e)}

    # 2. Verify MX host actually resolves (A/AAAA record exists)
    if not _mx_host_resolves(primary_mx):
        return {"valid": False, "mx": primary_mx,
                "error": f"MX host {primary_mx} does not resolve (NXDOMAIN)"}

    return {"valid": True, "mx": primary_mx, "error": None}

def batch_validate_csv(input_csv: str, output_csv: str = None):
    """
    Reads a CSV, validates 'Email' column, and adds 'Email_Valid' and 'MX_Record' columns.
    """
    import pandas as pd

    if output_csv is None:
        output_csv = input_csv

    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print(f"File not found: {input_csv}")
        return

    if "Email" not in df.columns:
        print("No 'Email' column found.")
        return

    print(f"Validating {len(df)} emails...")

    validation_results = []

    for email in df["Email"]:
        email = str(email).strip()
        if not email or email.lower() == 'nan':
            validation_results.append({"valid": False, "mx": None})
            continue

        res = validate_email(email)
        validation_results.append(res)

    df["Email_Valid"] = [res["valid"] for res in validation_results]
    df["MX_Record"] = [res["mx"] for res in validation_results]

    # Filter out invalid emails (optional, or just flag them)
    # For now, let's keep them but maybe clear the Email field if invalid?
    # Better to keep the data but flag it.

    df.to_csv(output_csv, index=False)
    print(f"Saved validated emails to {output_csv}")

    valid_count = df["Email_Valid"].sum()
    print(f"Valid emails: {valid_count}/{len(df)}")

if __name__ == "__main__":
    # Test
    print(validate_email("test@google.com"))
    print(validate_email("invalid@nonexistentdomain12345.com"))
