namespace HiddenViperFormal

inductive Evidence where
  | supports
  | contradicts
  | unknown
deriving Repr, DecidableEq

inductive Verdict where
  | verified
  | contradicted
  | unverified
deriving Repr, DecidableEq

def classify : Evidence → Verdict
  | .supports => .verified
  | .contradicts => .contradicted
  | .unknown => .unverified

theorem verified_iff_supports (e : Evidence) :
    classify e = .verified ↔ e = .supports := by
  cases e <;> simp [classify]

theorem contradicted_iff_contradicts (e : Evidence) :
    classify e = .contradicted ↔ e = .contradicts := by
  cases e <;> simp [classify]

theorem unknown_is_unverified :
    classify .unknown = .unverified := rfl

inductive ToolResult where
  | succeeded
  | failed
deriving Repr, DecidableEq

structure ClaimCheck where
  tool : ToolResult
  evidence : Evidence
deriving Repr, DecidableEq

def verdict (c : ClaimCheck) : Verdict :=
  classify c.evidence

theorem tool_success_without_evidence_is_unverified :
    verdict { tool := .succeeded, evidence := .unknown } = .unverified := rfl

theorem tool_success_with_contradiction_is_contradicted :
    verdict { tool := .succeeded, evidence := .contradicts } = .contradicted := rfl

theorem tool_success_with_support_is_verified :
    verdict { tool := .succeeded, evidence := .supports } = .verified := rfl

end HiddenViperFormal
