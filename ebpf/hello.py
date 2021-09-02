#!/usr/bin/env python2

from bcc import BPF

program = """
int hello_world(void *ctx) {
   bpf_trace_printk("foo\\n");
   return 0;
}
"""

bpf = BPF(text=program)
clone = bpf.get_syscall_fnname("clone")
bpf.attach_kprobe(event=clone, fn_name="hello_world")

while True:
    try:
        print(bpf.trace_fields())
    except KeyboardInterrupt:
        break
