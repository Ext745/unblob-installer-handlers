"""Setup Factory pure core (FSD §8): PKWARE scripts of Setup Factory 8 and 9."""

from unblob_installers import _blast


def test_tc_sf_05_pkware_decodes_blast_c_vector():
    # The example in zlib contrib/blast/blast.c.
    assert _blast.decompress(bytes.fromhex("00048224258f807f"), 100) == b"AIAIAIAIAIAIA"
