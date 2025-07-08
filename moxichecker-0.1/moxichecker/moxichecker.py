import argparse
import logging
import json
from typing import Optional
from pysmt.shortcuts import Not
from moxichecker import __version__
from moxichecker.moxi2smt import (
    get_check_system,
    get_define_system,
    get_logic,
    get_query,
    TransitionSystem,
)
from moxichecker.model_checking import MC_ALGORITHMS, get_prover


def _get_args(argv: Optional[list]) -> argparse.Namespace:
    # default values
    DEFAULT_ALG = "kind"
    DEFAULT_SOLVER = "msat"

    parser = argparse.ArgumentParser(description="MoXIchecker: MoXI Model Checker")

    parser.add_argument(
        "-m",
        "--mc-alg",
        metavar="STR",
        required=False,
        choices=MC_ALGORITHMS,
        default=DEFAULT_ALG,
        help=f"the model-checking algorithm to run (default: '{DEFAULT_ALG}')",
    )
    parser.add_argument(
        "-s",
        "--solver",
        metavar="STR",
        required=False,
        choices=["btor", "cvc5", "msat", "yices", "z3"],
        default=DEFAULT_SOLVER,
        help=f"the backend SMT solver to use (default: '{DEFAULT_SOLVER}')",
    )
    parser.add_argument(
        "--debug",
        help="show debugging messages",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "--version",
        help="print the tool version and exit",
        action="version",
        version=__version__,
    )
    parser.add_argument(
        "moxi_json",
        metavar="FILE",
        help="the verification task in the MoXI-JSON format",
    )
    kind_group = parser.add_argument_group("options for BMC/k-induction")
    kind_group.add_argument(
        "--no-simple-path",
        action="store_false",
        dest="use_simple_path",
        help="disable simple-path constraint for k-induction",
        required=False,
    )
    kind_group.add_argument(
        "--incr-solving",
        action="store_true",
        help="enable incremental SMT solving",
        required=False,
    )
    return parser.parse_args(argv)


def main(argv: Optional[list] = None):
    args = _get_args(argv)
    logging.basicConfig(
        format="[%(levelname)s] %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
    )
    logging.debug("MoXIchecker version: %s", __version__)
    logging.debug("Used configuration: %s", args)

    with open(args.moxi_json) as f:
        moxi_json = json.load(f)
    logic = get_logic(moxi_json)
    check_sys_cmd = get_check_system(moxi_json)
    def_sys_cmd = get_define_system(moxi_json, check_sys_cmd["symbol"])

    system = TransitionSystem(def_sys_cmd, logic)
    query_name, query = get_query(check_sys_cmd, logic)

    logging.info(
        "Checking reachability of query '%s' of system '%s'", query_name, system.name
    )
    logging.info("Used theory: %s", logic)
    prover = get_prover(args, system)
    verdict = prover.check_property(Not(query))
    logging.info("Model-checking result: %s", "UNREACHABLE" if verdict else "REACHABLE")


if __name__ == "__main__":
    main()
