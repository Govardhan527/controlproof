"""Every control controlproof ships, by 800-53 id (ADR-0007)."""

from controlproof.controls import Control
from controlproof.controls.ac_2 import AccountManagement
from controlproof.controls.au_2 import MultiRegionTrail
from controlproof.controls.ia_2_2 import MfaForConsoleUsers
from controlproof.controls.ia_5_1 import PasswordPolicy
from controlproof.controls.sc_7 import AdminPortsClosed
from controlproof.controls.sc_28 import EbsEncryptionByDefault
from controlproof.controls.sc_28_1 import S3DefaultKmsEncryption
from controlproof.controls.si_7_1 import LogFileValidation

REGISTRY: dict[str, type[Control]] = {
    control.id: control
    for control in (
        AccountManagement,
        AdminPortsClosed,
        EbsEncryptionByDefault,
        LogFileValidation,
        MfaForConsoleUsers,
        MultiRegionTrail,
        PasswordPolicy,
        S3DefaultKmsEncryption,
    )
}
