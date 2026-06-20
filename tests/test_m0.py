from src.m0_ingestion.processors.chunker import _approx_tokens
from src.m0_ingestion.processors.normalizer import normalize_publisher, strip_html


def test_strip_html():
    html_content = "<div><h1>Headline</h1><p>This is the <b>article</b> text.</p></div>"
    clean_text = strip_html(html_content)
    assert clean_text == "Headline This is the article text."

def test_normalize_publisher():
    assert normalize_publisher("Fox News") == "foxnews"
    assert normalize_publisher("The New York Times") == "nyt"
    assert normalize_publisher("Al Jazeera") == "aljazeera"
    assert normalize_publisher("Random Local News") == "randomlocalnews"

def test_approx_tokens():
    text = "This is a test of the token approximation logic."
    assert _approx_tokens(text) == 12
