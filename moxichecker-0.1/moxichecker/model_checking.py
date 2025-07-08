import logging
from argparse import Namespace
from typing import Optional
from pysmt.shortcuts import (
    TRUE,
    Not,
    And,
    Or,
    EqualsOrIff,
    Solver,
)
from pysmt.fnode import FNode
from moxichecker.moxi2smt import next_var, at_time, TransitionSystem


MC_ALGORITHMS = {"bmc", "kind", "pdr"}


def _push_assertion(solver: Solver, formula: FNode) -> None:
    solver.add_assertion(formula)
    solver.push()


class MCAlgorithm:
    def __init__(self, system: TransitionSystem, solver: str):
        raise NotImplementedError()

    def check_property(self, prop: FNode) -> bool:
        """Builds True is the property is satisfied, False otherwise."""
        raise NotImplementedError()


class BMCInductionBase(MCAlgorithm):
    def __init__(
        self,
        system: TransitionSystem,
        solver: str,
        check_ind: bool = True,
        use_simple_path: bool = True,
    ):
        self.system = system
        self.check_ind = check_ind
        self.use_simple_path = use_simple_path
        self.prime_map = {v: next_var(v) for v in self.system.variables}
        self.bmc_solver = Solver(name=solver, logic=system.logic)
        self.ind_solver = Solver(name=solver, logic=system.logic)

    def __del__(self):
        self.bmc_solver.exit()
        self.ind_solver.exit()

    def _get_subs(self, i: int) -> dict:
        """Builds a map from x to x@i and from x' to x@(i+1), for all x in system."""
        subs_i = {}
        for v in self.system.variables:
            subs_i[v] = at_time(v, i)
            subs_i[next_var(v)] = at_time(v, i + 1)
        return subs_i


class BMCInduction(BMCInductionBase):
    def check_property(self, prop: FNode) -> bool:
        """Interleaves BMC and K-Ind to verify the property."""
        logging.debug("Checking property %s...", prop)
        b = 0
        while True:
            f = self._get_bmc_query(prop, b)
            logging.debug("BMC: Checking bound %d...", b)
            if self.bmc_solver.is_sat(f):
                logging.info("Query reached at step %d", b)
                return False
            if self.check_ind:
                f = self._get_kind_query(prop, b)
                logging.debug("IND: Checking bound %d...", b)
                if self.ind_solver.is_unsat(f):
                    logging.info("Induction check passed at step %d", b)
                    return True
            b += 1

    def _get_unrolling(self, k: int) -> FNode:
        """Unrolling of the transition relation from 0 to k:

        E.g. T(0,1) & Inv(1) & T(1,2) & Inv(2) & ... & T(k-1,k) & Inv(k)
        """
        inv_next = self.system.inv.substitute(self.prime_map)
        res = []
        for i in range(k):
            subs_i = self._get_subs(i)
            res.append(self.system.trans.substitute(subs_i))
            res.append(inv_next.substitute(subs_i))
        return And(res)

    def _get_simple_path(self, k: int) -> FNode:
        """Simple path constraint for k-induction:
        each time encodes a different state
        """
        res = []
        for i in range(k):
            subs_i = self._get_subs(i)
            for j in range(i + 1, k):
                state = []
                subs_j = self._get_subs(j)
                for v in self.system.variables:
                    v_i = v.substitute(subs_i)
                    v_j = v.substitute(subs_j)
                    state.append(Not(EqualsOrIff(v_i, v_j)))
                res.append(Or(state))
        return And(res)

    def _get_k_hypothesis(self, prop: FNode, k: int) -> FNode:
        """Hypothesis for k-induction: each state up to k-1 fulfills the property"""
        res = []
        for i in range(k):
            subs_i = self._get_subs(i)
            res.append(prop.substitute(subs_i))
        return And(res)

    def _get_bmc_query(self, prop: FNode, k: int) -> FNode:
        """Returns the BMC encoding at step k"""
        subs_0 = self._get_subs(0)
        init_0 = self.system.init.substitute(subs_0)
        inv_0 = self.system.inv.substitute(subs_0)
        prop_k = prop.substitute(self._get_subs(k))
        return And(self._get_unrolling(k), init_0, inv_0, Not(prop_k))

    def _get_kind_query(self, prop: FNode, k: int) -> FNode:
        """Returns the K-Induction encoding at step K"""
        inv_0 = self.system.inv.substitute(self._get_subs(0))
        prop_k = prop.substitute(self._get_subs(k))
        return And(
            inv_0,
            self._get_unrolling(k),
            self._get_k_hypothesis(prop, k),
            self._get_simple_path(k) if self.use_simple_path else TRUE(),
            Not(prop_k),
        )


class BMCInductionIncr(BMCInductionBase):
    def check_property(self, prop: FNode) -> bool:
        logging.debug("Checking property %s...", prop)
        b = 0
        while True:
            not_prop_b = Not(prop.substitute(self._get_subs(b)))
            self._push_bmc_constr(b)
            logging.debug("BMC: Checking bound %d...", b)
            if self.bmc_solver.is_sat(not_prop_b):
                logging.info("Query reached at step %d", b)
                return False
            if self.check_ind:
                self._push_kind_constr(b, prop)
                logging.debug("IND: Checking bound %d...", b)
                if self.ind_solver.is_unsat(not_prop_b):
                    logging.info("Induction check passed at step %d", b)
                    return True
            b += 1

    def _push_bmc_constr(self, k: int) -> None:
        if k == 0:
            subs_0 = self._get_subs(0)
            init_0 = self.system.init.substitute(subs_0)
            inv_0 = self.system.inv.substitute(subs_0)
            _push_assertion(self.bmc_solver, And(init_0, inv_0))
        else:
            subs_map = self._get_subs(k - 1)
            _push_assertion(self.bmc_solver, self._get_trans_step(subs_map))

    def _push_kind_constr(self, k: int, prop: FNode) -> None:
        if k == 0:
            _push_assertion(
                self.ind_solver, self.system.inv.substitute(self._get_subs(0))
            )
            return
        subs_map = self._get_subs(k - 1)
        trans = self._get_trans_step(subs_map)
        # build hypothesis
        hypo = prop.substitute(subs_map)
        # simple-path constraints
        sp_constrs = []
        if self.use_simple_path:
            for i in range(k - 1):
                state = []
                subs_i = self._get_subs(i)
                for v in self.system.variables:
                    v_i = v.substitute(subs_i)
                    v_j = v.substitute(subs_map)
                    state.append(Not(EqualsOrIff(v_i, v_j)))
                sp_constrs.append(Or(state))
        sp_constrs = And(sp_constrs)
        _push_assertion(self.ind_solver, And(trans, hypo, sp_constrs))

    def _get_trans_step(self, subs_map: dict) -> FNode:
        trans = And(
            self.system.trans,
            self.system.inv.substitute(self.prime_map),
        )
        return trans.substitute(subs_map)


class PDR(MCAlgorithm):
    def __init__(self, system: TransitionSystem, solver: str):
        self.system = system
        self.frames = [And(system.init, system.inv)]
        self.solver = Solver(name=solver, logic=system.logic)
        self.prime_map = {v: next_var(v) for v in self.system.variables}

    def check_property(self, prop: FNode) -> bool:
        """Property Directed Reachability approach without optimizations."""
        logging.debug("Checking property %s...", prop)

        while True:
            cube = self._get_bad_state(prop)
            if cube is not None:
                # Blocking phase of a bad state
                if self._recursive_block(cube):
                    logging.info("Query reached at frame %d", len(self.frames) - 1)
                    return False
                else:
                    logging.debug("PDR: Cube blocked '%s'", str(cube))
            else:
                # Checking if the last two frames are equivalent i.e., are inductive
                if self._is_inductive():
                    logging.info(
                        "Fixed-point reached at frame %d", len(self.frames) - 1
                    )
                    return True
                else:
                    logging.debug("PDR: Adding frame %d...", (len(self.frames)))
                    self.frames.append(self.system.inv)

    def _get_bad_state(self, prop: FNode) -> Optional[FNode]:
        """Extracts a reachable state that intersects the negation
        of the property and the last current frame"""
        return self._solve(And(self.frames[-1], Not(prop)))

    def _solve(self, formula: FNode) -> Optional[FNode]:
        """Provides a satisfiable assignment to the state variables that are consistent with the input formula"""
        if self.solver.solve([formula]):
            return And(
                [
                    EqualsOrIff(v, self.solver.get_value(v))
                    for v in self.system.variables
                ]
            )
        return None

    def _recursive_block(self, cube: FNode) -> bool:
        """Blocks the cube at each frame, if possible.

        Returns True if the cube cannot be blocked.
        """
        for i in range(len(self.frames) - 1, 0, -1):
            cubeprime = cube.substitute(self.prime_map)
            cubepre = self._solve(
                And(
                    self.frames[i - 1],
                    self.system.trans,
                    self.system.inv.substitute(self.prime_map),
                    Not(cube),
                    cubeprime,
                )
            )
            if cubepre is None:
                for j in range(1, i + 1):
                    self.frames[j] = And(self.frames[j], Not(cube))
                return False
            cube = cubepre
        return True

    def _is_inductive(self) -> bool:
        """Checks if last two frames are equivalent"""
        if (
            len(self.frames) > 1
            and self._solve(Not(EqualsOrIff(self.frames[-1], self.frames[-2]))) is None
        ):
            return True
        return False

    def __del__(self):
        self.solver.exit()


def get_prover(args: Namespace, system: TransitionSystem) -> MCAlgorithm:
    if args.mc_alg in {"bmc", "kind"}:
        check_ind = args.mc_alg == "kind"
        mcer = BMCInductionIncr if args.incr_solving else BMCInduction
        return mcer(
            system,
            args.solver,
            check_ind=check_ind,
            use_simple_path=args.use_simple_path,
        )
    elif args.mc_alg == "pdr":
        return PDR(system, args.solver)
    else:
        raise ValueError(f"Unsupported model-checking algorithm '{args.mc_alg}'")
