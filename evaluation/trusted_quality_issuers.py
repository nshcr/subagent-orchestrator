"""Package-anchored public keys trusted to sign evaluation quality authority."""

TRUSTED_QUALITY_ISSUERS = {
    "evaluation-harness-2026": {
        "keys": {
            "rsa-2026-08": {
                "algorithm": "rsa-pkcs1-v1_5-sha256",
                "exponent": 65537,
                "modulus": int(
                    "b15e2ac10a1143a569be7509a7524596d20cb9068ebe87f0e0b8716e65c7ef9e"
                    "1c7391e3a6b862ac479696c394f49cc906b30eaf12d2c220d3c21d43927c2ad8"
                    "a21ac2d10119e7cbb42bc37fe29c333df41fea229ee8a2b7f897f59cd6fb3f57"
                    "43bdd6dba00140c606424680c0623983bfd4d247b91ffca9813e3bd3eeb7618f9"
                    "716931f9163a1c194e49e44cd22fd602a011dbf357cc6dc37b9d3ca93cef2f7b"
                    "83868a2bcb14f8d78af3364f5c7aed82e5fa887f7f836545fbfff9373d1371513"
                    "1ba1876e60b02d124b3778e7be0802c3fbb3877973f0250a9b2afe0549d351552"
                    "c023708468d068b1b4f320dcc860683876df06c434d58121c52da8a0d3cdd",
                    16,
                ),
                "scopes": ("development", "sealed"),
            }
        }
    }
}
