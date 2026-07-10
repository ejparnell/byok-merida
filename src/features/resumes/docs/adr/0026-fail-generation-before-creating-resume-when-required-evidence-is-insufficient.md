# Fail generation before creating Resume when required evidence is insufficient

Low Fit Score does not automatically block Job-Specific Resume generation if direct or adjacent evidence exists for at least one required skill, responsibility, or other required Fit Requirement. When no required Fit Requirement has direct or adjacent Master Resume evidence, the workflow fails before creating the Resume page and returns an `insufficient Master Resume evidence` error so the Job Posting stays in the Resume Creation Queue instead of gaining a misleading related Resume.

Supported-but-modest opportunities can still generate. Job-specific emphasis must be backed by direct or adjacent fit evidence, while the full work-experience draft can also include truthful Master Resume bullets that preserve work history without claiming to satisfy unsupported requirements.
