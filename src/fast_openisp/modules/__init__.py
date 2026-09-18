"""ISP modules, registered in pipeline order."""

from fast_openisp.config import MODULE_ORDER

from .aaf import AAF
from .awb import AWB
from .base import Context, ISPModule, PipelineData, PipelineError, SaturationValues
from .bcc import BCC
from .blc import BLC
from .bnf import BNF
from .ccm import CCM
from .ceh import CEH
from .cfa import CFA
from .cnf import CNF
from .csc import CSC
from .dpc import DPC
from .eeh import EEH
from .fcs import FCS
from .gac import GAC
from .hsc import HSC
from .nlm import NLM
from .scl import SCL

MODULE_CLASSES: dict[str, type[ISPModule]] = {
    cls.name: cls
    for cls in (DPC, BLC, AAF, AWB, CNF, CFA, CCM, GAC, CSC, NLM, BNF, CEH, EEH, FCS, HSC, BCC, SCL)
}
assert tuple(MODULE_CLASSES) == MODULE_ORDER

__all__ = [
    "MODULE_CLASSES",
    "Context",
    "ISPModule",
    "PipelineData",
    "PipelineError",
    "SaturationValues",
]
