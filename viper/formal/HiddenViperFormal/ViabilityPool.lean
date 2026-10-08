namespace HiddenViperFormal

abbrev Pool (α : Type) := α → Prop

def refine {α : Type} (pool constraint : Pool α) : Pool α :=
  fun x => pool x ∧ constraint x

def eliminated {α : Type} (pool constraint : Pool α) : Pool α :=
  fun x => pool x ∧ ¬ constraint x

theorem sound_refinement_preserves_truth
    {α : Type}
    (truth pool constraint : Pool α)
    (hPool : ∀ x, truth x → pool x)
    (hConstraint : ∀ x, truth x → constraint x) :
    ∀ x, truth x → refine pool constraint x := by
  intro x hx
  exact ⟨hPool x hx, hConstraint x hx⟩

theorem sound_hard_filter_never_eliminates_true
    {α : Type}
    (truth pool constraint : Pool α)
    (hSound : ∀ x, truth x → constraint x) :
    ∀ x, truth x → ¬ eliminated pool constraint x := by
  intro x hxTruth hxEliminated
  exact hxEliminated.2 (hSound x hxTruth)

inductive ConstraintClass where
  | hard
  | soft
deriving Repr, DecidableEq

structure Constraint (α : Type) where
  kind : ConstraintClass
  accepts : α → Prop

def activeAfter {α : Type} (pool : Pool α) (c : Constraint α) : Pool α :=
  match c.kind with
  | .hard => refine pool c.accepts
  | .soft => pool

theorem soft_constraint_never_removes_candidate
    {α : Type}
    (pool : Pool α)
    (accepts : α → Prop)
    (x : α) :
    activeAfter pool { kind := .soft, accepts := accepts } x ↔ pool x := by
  rfl

end HiddenViperFormal
