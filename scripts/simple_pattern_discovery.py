#!/usr/bin/env python3
"""Simple rule-based pattern discovery (no LLM calls).

Bypasses Claude SDK issues by using simple keyword clustering.
"""

import json
import yaml
from pathlib import Path
from collections import defaultdict
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent

def discover_patterns_simple(tickets: list[dict], min_size: int = 3) -> list[dict]:
    """Simple keyword-based pattern discovery."""

    # Group by component keywords
    component_groups = defaultdict(list)

    for ticket in tickets:
        query = ticket['turns'][0]['query'].lower()
        ticket_id = ticket['conversation_group_id']

        # Keyword matching
        if 'rpm-ostree' in query or 'ostree' in query:
            component_groups['rpm-ostree'].append(ticket_id)
        elif 'firewall' in query or 'firewalld' in query:
            component_groups['firewall'].append(ticket_id)
        elif 'podman' in query or 'container' in query:
            component_groups['containers'].append(ticket_id)
        elif 'systemd' in query or 'systemctl' in query:
            component_groups['systemd'].append(ticket_id)
        elif 'insights' in query:
            component_groups['insights'].append(ticket_id)
        elif 'grub' in query or 'boot' in query:
            component_groups['boot'].append(ticket_id)
        elif 'selinux' in query:
            component_groups['selinux'].append(ticket_id)
        elif 'samba' in query:
            component_groups['samba'].append(ticket_id)
        elif 'package' in query or 'dnf' in query or 'yum' in query:
            component_groups['packages'].append(ticket_id)
        elif 'network' in query or 'ip' in query or 'route' in query:
            component_groups['networking'].append(ticket_id)
        else:
            component_groups['other'].append(ticket_id)

    # Create patterns (only groups with >= min_size tickets)
    patterns = []
    for component, ticket_ids in component_groups.items():
        if len(ticket_ids) >= min_size:
            patterns.append({
                'pattern_id': f"{component.upper()}_PATTERN",
                'description': f"Questions about {component} functionality",
                'ticket_count': len(ticket_ids),
                'representative_tickets': ticket_ids[:3],
                'matched_tickets': ticket_ids,
                'common_problem_type': 'OTHER',
                'common_components': [component],
                'version_pattern': 'N/A',
                'verification_queries': [],
            })

    return patterns


def main():
    input_file = REPO_ROOT / 'config' / 'extracted_tickets.yaml'
    output_report = REPO_ROOT / 'config' / 'patterns_report.json'
    output_tagged = REPO_ROOT / 'config' / 'tickets_with_patterns.yaml'

    # Load tickets
    with open(input_file) as f:
        data = yaml.safe_load(f)

    rhel_tickets = [
        t for t in data['tickets']
        if not t.get('description', '').startswith('OUT_OF_SCOPE')
    ]

    print(f"Discovering patterns for {len(rhel_tickets)} RHEL tickets...")

    # Simple pattern discovery
    patterns = discover_patterns_simple(rhel_tickets, min_size=3)

    print(f"\nFound {len(patterns)} patterns:")
    for p in patterns:
        print(f"  {p['pattern_id']}: {p['ticket_count']} tickets")

    # Build ticket-to-pattern map
    ticket_to_pattern = {}
    for pattern in patterns:
        for ticket_id in pattern['matched_tickets']:
            ticket_to_pattern[ticket_id] = pattern['pattern_id']

    # Tag tickets
    tagged_tickets = []
    for ticket in data['tickets']:
        tagged = ticket.copy()
        pattern_id = ticket_to_pattern.get(ticket['conversation_group_id'])
        tagged['pattern_id'] = pattern_id
        tagged_tickets.append(tagged)

    # Save tagged YAML
    tagged_output = {
        'metadata': {
            **data['metadata'],
            'pattern_discovery_at': datetime.utcnow().isoformat(),
            'patterns_found': len(patterns),
            'ungrouped_tickets': sum(1 for t in tagged_tickets if not t.get('pattern_id')),
        },
        'tickets': tagged_tickets,
    }

    with open(output_tagged, 'w') as f:
        yaml.dump(tagged_output, f, default_flow_style=False, sort_keys=False)

    # Save pattern report
    total_grouped = sum(p['ticket_count'] for p in patterns)
    report = {
        'generated_at': datetime.utcnow().isoformat(),
        'summary': {
            'total_tickets': len(rhel_tickets),
            'patterns_found': len(patterns),
            'tickets_grouped': total_grouped,
            'tickets_ungrouped': len(rhel_tickets) - total_grouped,
            'grouping_rate': f"{(total_grouped / len(rhel_tickets) * 100):.1f}%",
            'method': 'rule-based (keyword matching)',
        },
        'patterns': patterns,
    }

    with open(output_report, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n✅ Saved:")
    print(f"  {output_report}")
    print(f"  {output_tagged}")
    print(f"\nGrouped: {total_grouped}/{len(rhel_tickets)} ({report['summary']['grouping_rate']})")


if __name__ == '__main__':
    main()
