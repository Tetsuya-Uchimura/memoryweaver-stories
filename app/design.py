"""Allowlisted book art direction, saved with each immutable edition.

AI collaborators can choose a recipe in Album.design. Older clients may omit it;
the publisher then selects from the supplied destination and cited place names.
No model-provided CSS, HTML, remote fonts, or scripts are accepted.
"""
DESIGNS = {"classic", "quiet", "editorial", "urban", "coastal"}


def choose_design(album, sources):
    explicit = album.get("design")
    if explicit in DESIGNS:
        return explicit
    cited = {sid for c in album["chapters"] for sid in c["source_ids"]}
    places = " ".join(s["location"]["name"] for s in sources if s["id"] in cited and s.get("location"))
    context = (album.get("location", "") + " " + places).casefold()
    if any(word in context for word in ("kyoto", "\u4eac\u90fd", "arashiyama", "kiyomizu")):
        return "quiet"
    if any(word in context for word in ("paris", "\u30d1\u30ea", "louvre", "montmartre")):
        return "editorial"
    if any(word in context for word in ("new york", "new-york", "\u30cb\u30e5\u30fc\u30e8\u30fc\u30af", "brooklyn", "manhattan")):
        return "urban"
    if any(word in context for word in ("santorini", "aegean", "ammoudi", "perissa")):
        return "coastal"
    return "classic"
