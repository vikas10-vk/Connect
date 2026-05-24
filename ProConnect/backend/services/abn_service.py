
import httpx


async def lookup_abn(abn: str) -> dict:
    """
    Look up ABN using the free ABR API.
    No API key required for basic lookups.
    """
    clean_abn = abn.replace(" ", "").replace("-", "")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                "https://abr.business.gov.au/json/AbnDetails.aspx",
                params={"abn": clean_abn, "callback": "callback"},
            )

            # ABR returns JSONP — strip the callback wrapper
            text = res.text
            if text.startswith("callback("):
                text = text[9:-1]

            import json
            data = json.loads(text)

            if data.get("AbnStatus") == "Active":
                return {
                    "valid":      True,
                    "abn":        data.get("Abn", clean_abn),
                    "name":       data.get("EntityName", ""),
                    "status":     data.get("AbnStatus", ""),
                    "type":       data.get("EntityTypeName", ""),
                    "state":      data.get("AddressState", ""),
                    "postcode":   data.get("AddressPostcode", ""),
                    "gst":        data.get("Gst", ""),
                }
            else:
                return {
                    "valid":  False,
                    "status": data.get("AbnStatus", "Not found"),
                    "name":   "",
                    "abn":    clean_abn,
                }
    except Exception:
        # Fallback — format check only
        return _validate_abn_format(clean_abn)


def _validate_abn_format(abn: str) -> dict:
    """
    Basic ABN format validation using the ATO weighting algorithm.
    Does not verify against the register — offline fallback only.
    """
    digits = abn.replace(" ", "")
    if len(digits) != 11 or not digits.isdigit():
        return {"valid": False, "status": "Invalid format", "name": "", "abn": abn}

    weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    d = [int(c) for c in digits]
    d[0] -= 1
    total = sum(w * v for w, v in zip(weights, d, strict=False))

    if total % 89 == 0:
        return {"valid": True, "status": "Format valid (unverified)", "name": "", "abn": abn}
    return {"valid": False, "status": "Invalid ABN", "name": "", "abn": abn}
