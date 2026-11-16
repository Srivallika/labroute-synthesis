"""Optional chemistry helpers. If RDKit is installed, SMILES are canonicalized."""

from functools import lru_cache

try:  # pragma: no cover
    from rdkit import Chem

    HAS_RDKIT = True
except ImportError:  # pragma: no cover
    Chem = None
    HAS_RDKIT = False


@lru_cache(maxsize=None)
def canonicalize_smiles(smiles: str) -> str:
    """Return a canonical SMILES if RDKit is available, otherwise the stripped input.
    """
    s = smiles.strip()
    if not HAS_RDKIT:
        return s
    mol = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(mol) if mol is not None else s
