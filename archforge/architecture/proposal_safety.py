from __future__ import annotations

from copy import deepcopy


def harden_design_agent(module):
    """Install an explicit advisory provenance contract on generated AI proposals.

    The design-agent generators contain heuristics and assumed engineering quantities.
    They are useful proposal inputs, but they are not a structural/physics solver.  This
    adapter preserves the existing API while preventing proposal approval from being
    confused with engineering verification.
    """
    original = module.AIAssistantProposal
    if getattr(original, '_archforge_provenance_hardened', False):
        return original

    class AdvisoryAIAssistantProposal(original):
        _archforge_provenance_hardened = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.validation_provenance = {
                'level': 'heuristic',
                'engineering_verified': False,
                'validator': None,
                'evidence_id': None,
            }
            # Keep legacy consumers working, but make the evidence level impossible to
            # miss for code that only sees the existing physics_validation dictionary.
            self.physics_validation = deepcopy(self.physics_validation)
            self.physics_validation['verification_level'] = 'heuristic'
            self.physics_validation['engineering_verified'] = False

        def to_dict(self):
            data = super().to_dict()
            data['validation_provenance'] = deepcopy(self.validation_provenance)
            data['physics_validation'] = deepcopy(self.physics_validation)
            return data

    AdvisoryAIAssistantProposal.__name__ = 'AIAssistantProposal'
    AdvisoryAIAssistantProposal.__qualname__ = 'AIAssistantProposal'
    module.AIAssistantProposal = AdvisoryAIAssistantProposal
    return AdvisoryAIAssistantProposal
