import ctypes
import shutil
import time
import os

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

def check_system():
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))

    total_gb = stat.ullTotalPhys / (1024 ** 3)
    avail_gb = stat.ullAvailPhys / (1024 ** 3)
    used_gb = total_gb - avail_gb

    total_d, used_d, free_d = shutil.disk_usage("d:\\")

    print(f"RAM Total: {total_gb:.1f} GB")
    print(f"RAM Used:  {used_gb:.1f} GB ({stat.dwMemoryLoad}%)")
    print(f"RAM Free:  {avail_gb:.1f} GB")
    print(f"Disk D: Free {free_d / (1024 ** 3):.1f} GB / {total_d / (1024 ** 3):.1f} GB")

if __name__ == "__main__":
    check_system()
