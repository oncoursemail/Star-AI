# Ghidra headless post-script: decompile a single named function and print it.
# Invoked by star.reverse_engineering.ghidra_decompile via analyzeHeadless
#   ... -postScript DecompileOne.py <function_name_or_address>
# Jython script (Ghidra's scripting runtime). Read-only: prints C to stdout,
# which the wrapper captures and truncates. No files are written, no network.
# @category STAR.RE
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor


def main():
    args = getScriptArgs()
    if not args:
        print("STAR_RE_ERROR: no function name supplied")
        return
    target = args[0]
    fm = currentProgram.getFunctionManager()
    match = None
    for fn in fm.getFunctions(True):
        if fn.getName() == target:
            match = fn
            break
    if match is None:
        # Try as an address.
        try:
            addr = currentProgram.getAddressFactory().getAddress(target)
            match = fm.getFunctionContaining(addr)
        except Exception:
            match = None
    if match is None:
        print("STAR_RE_ERROR: function not found: %s" % target)
        return
    iface = DecompInterface()
    iface.openProgram(currentProgram)
    result = iface.decompileFunction(match, 60, ConsoleTaskMonitor())
    if result is not None and result.decompileCompleted():
        print("STAR_RE_BEGIN %s" % match.getName())
        print(result.getDecompiledFunction().getC())
        print("STAR_RE_END")
    else:
        print("STAR_RE_ERROR: decompilation did not complete for %s" % target)


main()
