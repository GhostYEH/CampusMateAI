import pytest

from app.utils.text_utils import chunk_text


@pytest.mark.parametrize("chunk_size, overlap", [(0, 0), (-1, 0), (4, -1), (4, 4), (4, 5)])
@pytest.mark.parametrize("text", ["", "abcdefghijklmnop"])
def test_invalid_chunk_parameters_fail_instead_of_looping(text, chunk_size, overlap):
    with pytest.raises(ValueError):
        chunk_text(text, chunk_size=chunk_size, overlap=overlap)


@pytest.mark.parametrize("overlap, expected", [
    (0, ["abcd", "efgh", "ij"]),
    (1, ["abcd", "defg", "ghij"]),
    (3, ["abcd", "bcde", "cdef", "defg", "efgh", "fghi", "ghij"]),
])
def test_valid_chunk_parameters_preserve_coverage_and_overlap(overlap, expected):
    assert chunk_text("abcdefghij", chunk_size=4, overlap=overlap) == expected
