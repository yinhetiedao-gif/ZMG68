"""F5-B backend gate/performance, actual full instance counts. No exports."""
import json
import sys
from time import perf_counter
from xiaomang_pattern_lab.fabric_base import BaseDefinition
from xiaomang_pattern_lab.fabric_cells import UnitCellDefinition
from xiaomang_pattern_lab.fabric_plan import FabricPlanner,RegularPlacement
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService,FabricFusionFailure

def process_peak_memory_mb():
    """Observed process-lifetime peak, not an incremental per-case estimate."""
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[
                (name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize',
                'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi=ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
            return counters.PeakWorkingSetSize/1024**2
    return None

for kind,count,cols,rows in [('pyramid',100,10,10),('cone',100,10,10),('fin',100,10,10),
    ('double_tower',100,10,10),('cylinder',100,10,10),('pyramid',400,20,20),
    ('pyramid',1000,20,50),('pyramid',5000,50,100)]:
    started=perf_counter()
    plan=FabricPlanner().plan((0,0,60,60),.6,UnitCellDefinition(kind,.3,.3,3),
        RegularPlacement(60/cols,60/rows),preview_limit=False)
    candidate=build_fabric_candidate(plan,BaseDefinition('solid',.6,0),(0,0,60,60),
        document_id='f5b-benchmark',document_revision=1)
    candidate_ms=(perf_counter()-started)*1000
    try:
        final=FabricFusionService().build(candidate)
        print(json.dumps({'kind':kind,'count':count,'candidate_ms':candidate_ms,
            'process_lifetime_peak_memory_mb':process_peak_memory_mb(),
            'status':'PASS','fusion_timings_ms':final.report['timings_ms'],
            'components':final.report['connected_component_count'],
            'degenerate_faces':final.report['validation_report']['degenerate_face_count'],
            'volume_mm3':final.report['volume_mm3'],'bounds':final.report['bounds_mm']},ensure_ascii=False),flush=True)
    except FabricFusionFailure as error:
        print(json.dumps({'kind':kind,'count':count,'candidate_ms':candidate_ms,
            'process_lifetime_peak_memory_mb':process_peak_memory_mb(),'status':'FAIL',**error.report},ensure_ascii=False),flush=True)
        if count != 5000:
            raise
