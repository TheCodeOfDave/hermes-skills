# API Method Map

## Scope

Load this reference for exact base-method families and signatures from the pinned NAPALM 5.2/develop source. Driver implementations may narrow support or add behavior; inspect the chosen driver before use.

## Constructor and lifecycle

```text
NetworkDriver(
    hostname: str,
    username: str,
    password: str,
    timeout: int = 60,
    optional_args: Optional[Dict] = None,
)
```

- `open(self) -> None`
- `close(self) -> None`
- `is_alive(self) -> AliveDict`
- `pre_connection_tests(self) -> None`
- `connection_tests(self) -> None`
- `post_connection_tests(self) -> None`
- `__enter__(self) -> NetworkDriver`
- `__exit__(...) -> Optional[Literal[False]]`

## Templates and configuration

```text
load_template(
    template_name: str,
    template_source: Optional[str] = None,
    template_path: Optional[str] = None,
    **template_vars: Any,
) -> None
```

```text
load_replace_candidate(
    filename: Optional[str] = None,
    config: Optional[str] = None,
) -> None
```

```text
load_merge_candidate(
    filename: Optional[str] = None,
    config: Optional[str] = None,
) -> None
```

- `compare_config(self) -> str`
- `commit_config(self, message: str = "", revert_in: Optional[int] = None) -> None`
- `confirm_commit(self) -> None`
- `has_pending_commit(self) -> bool`
- `discard_config(self) -> None`
- `rollback(self) -> None`

## Identity and interfaces

- `get_facts(self) -> FactsDict`
- `get_interfaces(self) -> Dict[str, InterfaceDict]`
- `get_interfaces_counters(self) -> Dict[str, InterfaceCounterDict]`
- `get_interfaces_ip(self) -> Dict[str, InterfacesIPDict]`
- `get_optics(self) -> Dict[str, OpticsDict]`
- `get_vlans(self) -> Dict[str, VlanDict]`

## Topology

- `get_lldp_neighbors(self) -> Dict[str, List[LLDPNeighborDict]]`
- `get_lldp_neighbors_detail(self, interface: str = "") -> LLDPNeighborsDetailDict`
- `get_arp_table(self, vrf: str = "") -> List[ARPTableDict]`
- `get_ipv6_neighbors_table(self) -> List[IPV6NeighborDict]`
- `get_mac_address_table(self) -> List[MACAdressTable]`

## Routing and BGP

- `get_bgp_neighbors(self) -> Dict[str, BGPStateNeighborsPerVRFDict]`
- `get_bgp_config(self, group: str = "", neighbor: str = "") -> BGPConfigGroupDict`
- `get_bgp_neighbors_detail(self, neighbor_address: str = "") -> Dict[str, PeerDetailsDict]`
- `get_route_to(self, destination: str = "", protocol: str = "", longer: bool = False) -> Dict[str, RouteDict]`
- `get_network_instances(self, name: str = "") -> Dict[str, NetworkInstanceDict]`

## Services and environment

- `get_environment(self) -> EnvironmentDict`
- `get_ntp_peers(self) -> Dict[str, NTPPeerDict]`
- `get_ntp_servers(self) -> Dict[str, NTPServerDict]`
- `get_ntp_stats(self) -> List[NTPStats]`
- `get_snmp_information(self) -> SNMPDict`
- `get_users(self) -> Dict[str, UsersDict]`
- `get_probes_config(self) -> Dict[str, ProbeTestDict]`
- `get_probes_results(self) -> Dict[str, ProbeTestResultDict]`
- `get_firewall_policies(self) -> Dict[str, List[FirewallPolicyDict]]`

## Configuration retrieval

```text
get_config(
    retrieve: str = "all",
    full: bool = False,
    sanitized: bool = False,
    format: str = "text",
) -> ConfigDict
```

Use `sanitized=True` when the driver supports it and configuration must be retained. Still inspect output for secrets.

## Raw command

```text
cli(
    commands: List[str],
    encoding: str = "text",
) -> Dict[str, Union[str, Dict[str, Any]]]
```

The output dictionary is keyed by command. `encoding` support can differ by driver.

## Ping

```text
ping(
    destination: str,
    source: str = PING_SOURCE,
    ttl: int = PING_TTL,
    timeout: int = PING_TIMEOUT,
    size: int = PING_SIZE,
    count: int = PING_COUNT,
    vrf: str = PING_VRF,
    source_interface: str = PING_SOURCE_INTERFACE,
) -> PingResultDict
```

## Traceroute

```text
traceroute(
    destination: str,
    source: str = TRACEROUTE_SOURCE,
    ttl: int = TRACEROUTE_TTL,
    timeout: int = TRACEROUTE_TIMEOUT,
    vrf: str = TRACEROUTE_VRF,
) -> TracerouteResultDict
```

## Compliance

```text
compliance_report(
    validation_file: Optional[str] = None,
    validation_source: Optional[list[dict]] = None,
) -> ReportResult
```

Pass one source form and inspect `complies`, `skipped`, and nested details. The 5.2.0 annotation says `Optional[str]`, but the implementation deep-copies and asserts that `validation_source` is a list of rule dictionaries; this map documents the runtime contract.

## Exception map

Base:

- `NapalmException`
- `ModuleImportError`

Connection:

- `ConnectionException`
- `ConnectAuthError`
- `ConnectTimeoutError`
- `ConnectionClosedException`
- `UnsupportedVersion`

Configuration/session:

- `ReplaceConfigException`
- `MergeConfigException`
- `CommitConfirmException`
- `CommitError`
- `LockError`
- `UnlockError`
- `SessionLockedException`

Command/template/validation:

- `CommandTimeoutException`
- `CommandErrorException`
- `DriverTemplateNotImplemented`
- `TemplateNotImplemented`
- `TemplateRenderException`
- `ValidationException`

`NotImplementedError` remains the standard unsupported-method signal in the driver contract.

## Method-selection rule

```text
check current support matrix
→ inspect exact driver implementation/signature
→ call on mock fixture
→ call on one real lab canary
→ record normalized shape and exceptions
→ authorize bounded use
```

## Source anchors

- `napalm/base/base.py`
- `napalm/base/models.py`
- `napalm/base/exceptions.py`
- generated `network-driver-api.json`
