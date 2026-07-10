# Use two-stage Fit Requirement matching

Resume Fit Analysis matches each Fit Requirement to Master Resume Evidence Items in two stages. The workflow first generates candidates with keyword coverage, normalized skill overlap, and section or category hints, then runs semantic similarity on that candidate set with a broader fallback when no lexical candidates are found, keeping the analysis explainable and cheaper while still catching meaningful wording differences.
