| eval icmp_type_text=case(
    icmp_type=0, "Echo Reply",
    icmp_type=3, "Destination Unreachable",
    icmp_type=5, "Redirect",
    icmp_type=8, "Echo Request",
    icmp_type=11, "Time Exceeded",
    icmp_type=12, "Parameter Problem",
    true(), "Unknown"
)
| eval icmp_code_text=case(
    icmp_type=3 AND icmp_code=0, "Network Unreachable",
    icmp_type=3 AND icmp_code=1, "Host Unreachable",
    icmp_type=3 AND icmp_code=2, "Protocol Unreachable",
    icmp_type=3 AND icmp_code=3, "Port Unreachable",
    icmp_type=3 AND icmp_code=4, "Fragmentation Needed",
    icmp_type=3 AND icmp_code=9, "Network Administratively Prohibited",
    icmp_type=3 AND icmp_code=10, "Host Administratively Prohibited",
    icmp_type=3 AND icmp_code=13, "Communication Administratively Prohibited",
    icmp_type=11 AND icmp_code=0, "TTL Exceeded",
    icmp_type=11 AND icmp_code=1, "Fragment Reassembly Time Exceeded",
    icmp_code=0, "No additional code",
    true(), "Unknown"
)
