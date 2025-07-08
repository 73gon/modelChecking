import logging
from pysmt.shortcuts import (
    TRUE,
    FALSE,
    Not,
    Implies,
    And,
    Or,
    Xor,
    EqualsOrIff,
    Ite,
    Symbol,
    Plus,
    Minus,
    Times,
    Div,
    LE,
    LT,
    GE,
    GT,
    BVAdd,
    BVSub,
    BVMul,
    BVUDiv,
    BVSDiv,
    BVURem,
    BVSRem,
    BVAnd,
    BVNot,
    BVOr,
    BVXor,
    BVLShl,
    BVLShr,
    BVAShr,
    BVULT,
    BVULE,
    BVUGT,
    BVUGE,
    BVSLT,
    BVSLE,
    BVSGT,
    BVSGE,
    BVConcat,
    BVExtract,
    BVZExt,
    BVSExt,
    BVRol,
    BVRor,
    Select,
    Store,
    BVNeg,
    BV,
    Real,
    Int,
)
from pysmt.typing import BVType, ArrayType, PySMTType, BOOL, REAL, INT
from pysmt.fnode import FNode

BOOL_OPERATIONS = {
    "true": lambda _: TRUE(),
    "false": lambda _: FALSE(),
    "not": lambda A: Not(A[0]),
    "=>": lambda A: Implies(A[0], A[1]),
    "and": lambda A: And(A),
    "or": lambda A: Or(A),
    "xor": lambda A: Xor(A[0], A[1]),
    "=": lambda A: EqualsOrIff(A[0], A[1]),
    "distinct": lambda A: Not(EqualsOrIff(A[0], A[1])),
    "ite": lambda A: Ite(A[0], A[1], A[2]),
}

INT_REAL_OPERATIONS = {
    "-": lambda A: Minus(Int(0), A[0]) if len(A) == 1 else Minus(A[0], A[1]),
    "+": lambda A: Plus(A[0], A[1]),
    "*": lambda A: Times(A[0], A[1]),
    "/": lambda A: Div(A[0], A[1]),
    "<=": lambda A: LE(A[0], A[1]),
    "<": lambda A: LT(A[0], A[1]),
    ">=": lambda A: GE(A[0], A[1]),
    ">": lambda A: GT(A[0], A[1]),
    "mod": lambda A: A[0] % A[1],
    "div": lambda A: A[0].div(A[1]),
    "abs": lambda A: A[0].abs(),
    "divisible": lambda A: A[0].divisible(A[1]),
}

BITVEC_OPERATIONS = {
    "bvadd": lambda A: BVAdd(A[0], A[1]),
    "bvsub": lambda A: BVSub(A[0], A[1]),
    "bvmul": lambda A: BVMul(A[0], A[1]),
    "bvudiv": lambda A: BVUDiv(A[0], A[1]),
    "bvsdiv": lambda A: BVSDiv(A[0], A[1]),
    "bvurem": lambda A: BVURem(A[0], A[1]),
    "bvsrem": lambda A: BVSRem(A[0], A[1]),
    "bvsmod": lambda A: BVSub(A[0], BVMul(A[1], BVUDiv(A[0], A[1]))),
    "bvand": lambda A: BVAnd(A[0], A[1]),
    "bvnand": lambda A: BVNot(BVAnd(A[0], A[1])),
    "bvor": lambda A: BVOr(A[0], A[1]),
    "bvnor": lambda A: BVNot(BVOr(A[0], A[1])),
    "bvxor": lambda A: BVXor(A[0], A[1]),
    "bvxnor": lambda A: BVNot(BVXor(A[0], A[1])),
    "bvshl": lambda A: BVLShl(A[0], A[1]),
    "bvlshr": lambda A: BVLShr(A[0], A[1]),
    "bvashr": lambda A: BVAShr(A[0], A[1]),
    "bvnot": lambda A: BVNot(A[0]),
    "bvneg": lambda A: BVNeg(A[0]),
    "bvult": lambda A: BVULT(A[0], A[1]),
    "bvule": lambda A: BVULE(A[0], A[1]),
    "bvugt": lambda A: BVUGT(A[0], A[1]),
    "bvuge": lambda A: BVUGE(A[0], A[1]),
    "bvslt": lambda A: BVSLT(A[0], A[1]),
    "bvsle": lambda A: BVSLE(A[0], A[1]),
    "bvsgt": lambda A: BVSGT(A[0], A[1]),
    "bvsge": lambda A: BVSGE(A[0], A[1]),
    "concat": lambda A: BVConcat(A[0], A[1]),
    "extract": lambda A: BVExtract(A[0], A[2], A[1]),
    "zero_extend": lambda A: BVZExt(A[0], int(A[1])),
    "sign_extend": lambda A: BVSExt(A[0], int(A[1])),
    "rotate_left": lambda A: BVRol(A[0], int(A[1])),
    "rotate_right": lambda A: BVRor(A[0], int(A[1])),
}

ARRAY_OPERATIONS = {
    "select": lambda A: Select(A[0], A[1]),
    "store": lambda A: Store(A[0], A[1], A[2]),
}

CONVERSION_OPERATIONS = {
    "to_real": lambda A: A[0].to_real(),
    "to_int": lambda A: A[0].to_int(),
    "is_int": lambda A: A[0].is_int(),
}

BV_LOGIC = {"QF_BV", "QF_ABV"}
INT_LOGIC = {"QF_LIA", "QF_NIA"}
REAL_LOGIC = {"QF_LRA", "QF_NRA"}
SUPPORTED_LOGIC = BV_LOGIC | INT_LOGIC | REAL_LOGIC


def next_var(var: FNode) -> FNode:
    return Symbol(f"next({var.symbol_name()})", var.symbol_type())


def at_time(var: FNode, t: int) -> FNode:
    return Symbol(f"{var.symbol_name()}@{t}", var.symbol_type())


def get_logic(commands: list) -> str:
    for cmd in commands:
        if cmd["command"] == "set-logic":
            # return the 1st command found
            logic = cmd["logic"]
            if logic not in SUPPORTED_LOGIC:
                raise ValueError(f"set-logic '{logic}' is not supported")
            return logic
    raise ValueError("No set-logic defined")


def get_define_system(commands: list, symbol: str) -> dict:
    for cmd in commands:
        if cmd["command"] == "define-system" and cmd["symbol"] == symbol:
            # return the 1st command found
            return cmd
    raise ValueError("System to be checked is not defined")


def get_check_system(commands: list) -> dict:
    for cmd in commands:
        if cmd["command"] == "check-system":
            # return the 1st command found
            return cmd
    raise ValueError("No system check specified")


class TransitionSystem:
    def __init__(self, def_sys_cmd: dict, logic: str):
        if len(def_sys_cmd.get("subsys", [])) > 0:
            raise ValueError("Subsystems are not supported")
        self.name = def_sys_cmd["symbol"]
        self.logic = logic
        var_map = _get_variables(def_sys_cmd)
        self.variables = list(var_map.values())
        logging.debug("Variables: %s", self.variables)
        self.init = _construct_formula(logic, var_map, def_sys_cmd["init"])
        logging.debug("Init formula: %s", self.init)
        self.trans = _construct_formula(logic, var_map, def_sys_cmd["trans"])
        logging.debug("Transition-relation formula: %s", self.trans)
        self.inv = _construct_formula(logic, var_map, def_sys_cmd["inv"])
        logging.debug("Invariant formula: %s", self.inv)


def get_query(check_sys_cmd: dict, logic: str) -> tuple[str, FNode]:
    var_map = _get_variables(check_sys_cmd)
    for query in check_sys_cmd["query"]:
        for formula in query["formulas"]:
            for reachables in check_sys_cmd["reachable"]:
                if reachables["symbol"] == formula:
                    # return the 1st property found
                    f = _construct_formula(logic, var_map, reachables["formula"])
                    logging.debug("Query Formula: %s", f)
                    return reachables["symbol"], f
    raise ValueError("No query specified")


def _bv_literal(value: str) -> FNode:
    if value.startswith("#b"):
        return BV(value)
    elif value.startswith("#x"):
        return BV(int(value[2:], 16), (len(value) - 2) * 4)
    else:
        raise ValueError(f"Invalid bitvector literal: {value}")


def _get_sort(sort: dict) -> PySMTType:
    if sort["identifier"]["symbol"] == "BitVec":
        size = sort["identifier"]["indices"][0]
        return BVType(size)
    elif sort["identifier"]["symbol"] == "Array":
        index_type = _get_sort(sort["parameters"][0])
        value_type = _get_sort(sort["parameters"][1])
        return ArrayType(index_type, value_type)
    elif sort["identifier"]["symbol"] == "Real":
        return REAL
    elif sort["identifier"]["symbol"] == "Bool":
        return BOOL
    elif sort["identifier"]["symbol"] == "Int":
        return INT
    else:
        raise ValueError(f"Unknown sort: {sort['identifier']['symbol']}")


def _get_variables(system_definition: dict) -> dict:
    variables = {}
    for var_type in ["input", "output", "local"]:
        if var_type in system_definition:
            for var in system_definition[var_type]:
                name = var["symbol"]
                sort = _get_sort(var["sort"])
                variables[name] = Symbol(name, sort)
    return variables


def _construct_formula(logic: str, variables: dict, prop: dict) -> FNode:
    identifier = prop["identifier"]
    if isinstance(identifier, dict):
        if "symbol" in identifier:
            symbol = identifier["symbol"]
            args = []
            if "args" in prop:
                for arg in prop["args"]:
                    args.append(_construct_formula(logic, variables, arg))
            if "indices" in identifier and identifier["indices"]:
                args.extend(identifier["indices"])
            if symbol == "const":
                return args[0]
            if symbol in BOOL_OPERATIONS:
                return BOOL_OPERATIONS[symbol](args)
            elif symbol in INT_REAL_OPERATIONS:
                return INT_REAL_OPERATIONS[symbol](args)
            elif symbol in BITVEC_OPERATIONS:
                return BITVEC_OPERATIONS[symbol](args)
            elif symbol in ARRAY_OPERATIONS:
                return ARRAY_OPERATIONS[symbol](args)
            elif symbol in CONVERSION_OPERATIONS:
                return CONVERSION_OPERATIONS[symbol](args)
            else:
                raise ValueError(f"Invalid symbol: {symbol}")
        else:
            raise ValueError(
                f"Invalid identifier format: missing 'symbol' key ({identifier})"
            )
    elif isinstance(identifier, str):
        if identifier in variables:
            return variables[identifier]
        elif identifier.endswith("'"):
            return next_var(variables[identifier[:-1]])
        elif identifier == "true":
            return TRUE()
        elif identifier == "false":
            return FALSE()
        elif logic in BV_LOGIC and identifier.startswith("#"):
            return _bv_literal(identifier)
        elif logic in REAL_LOGIC:
            return Real(float(identifier))
        elif logic in INT_LOGIC:
            return Int(int(identifier))
        else:
            raise ValueError(f"Unknown identifier: {identifier}")
    else:
        raise ValueError("Identifier is neither dict or str")
