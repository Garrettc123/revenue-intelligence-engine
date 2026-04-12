"""
GARCAR REVENUE INTELLIGENCE ENGINE
====================================
RHNS-Powered Autonomous Revenue Monitoring System

Reason: Analyzes all revenue signals
Harmony: Aligns across Stripe, HubSpot, Shopify, Linear  
Navigation: Routes opportunities to correct close actions
Standards: Enforces revenue quality gates

Revenue Streams Monitored:
- Stripe payment intents and subscriptions
- HubSpot deal pipeline
- Shopify orders
- Gumroad sales
- Linear billing/contract issues
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict

@dataclass
class RevenueSignal:
    source: str
    signal_type: str  # opportunity | churn_risk | payment_failed | new_lead | upsell
    value_usd: float
    confidence: float  # 0.0 - 1.0
    action_required: str
    urgency: str  # immediate | high | medium | low
    timestamp: str
    metadata: dict

class RHNSRevenueEngine:
    """RHNS-powered autonomous revenue decision engine."""
    
    def __init__(self):
        self.stripe_key = os.getenv('STRIPE_SECRET_KEY', '')
        self.hubspot_key = os.getenv('HUBSPOT_API_KEY', '')
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL', '')
        self.linear_key = os.getenv('LINEAR_API_KEY', '')
        self.signals: list[RevenueSignal] = []
        
    def reason(self, data: dict) -> dict:
        """RHNS Layer 1: Reason — extract first-principles signal from raw data."""
        signal_type = 'opportunity'
        urgency = 'medium'
        confidence = 0.7
        
        if data.get('type') == 'payment_intent.payment_failed':
            signal_type = 'payment_failed'
            urgency = 'immediate'
            confidence = 1.0
        elif data.get('type') == 'customer.subscription.deleted':
            signal_type = 'churn_risk'
            urgency = 'immediate'
            confidence = 0.95
        elif data.get('type') == 'payment_intent.succeeded':
            signal_type = 'revenue_confirmed'
            urgency = 'low'
            confidence = 1.0
            
        return {
            'signal_type': signal_type,
            'urgency': urgency,
            'confidence': confidence
        }
    
    def harmonize(self, signals: list) -> list:
        """RHNS Layer 2: Harmony — align signals across all revenue sources."""
        # Deduplicate, rank by urgency and value
        seen = set()
        harmonized = []
        urgency_rank = {'immediate': 0, 'high': 1, 'medium': 2, 'low': 3}
        
        for s in sorted(signals, key=lambda x: urgency_rank.get(x.urgency, 4)):
            key = f"{s.source}:{s.signal_type}"
            if key not in seen:
                seen.add(key)
                harmonized.append(s)
        return harmonized
    
    def navigate(self, signal: RevenueSignal) -> str:
        """RHNS Layer 3: Navigate — determine the optimal action path."""
        if signal.signal_type == 'payment_failed':
            return f"RETRY_PAYMENT: Contact {signal.metadata.get('customer', 'unknown')} within 2h. Value: ${signal.value_usd:.2f}"
        elif signal.signal_type == 'churn_risk':
            return f"RETENTION_SEQUENCE: Fire win-back campaign for ${signal.value_usd:.2f}/mo at-risk revenue"
        elif signal.signal_type == 'opportunity':
            return f"PIPELINE_ADD: Add to HubSpot deal stage. Estimated value ${signal.value_usd:.2f}"
        elif signal.signal_type == 'upsell':
            return f"UPSELL_TRIGGER: Present upgrade offer. Incremental value ${signal.value_usd:.2f}"
        return "MONITOR: Track signal for 24h before action"
    
    def enforce_standards(self, action: str, signal: RevenueSignal) -> dict:
        """RHNS Layer 4: Standards — quality gate before execution."""
        return {
            'action': action,
            'approved': signal.confidence >= 0.6,
            'reason': 'Confidence threshold met' if signal.confidence >= 0.6 else 'Below confidence threshold — human review required',
            'signal': asdict(signal)
        }
    
    def check_stripe(self) -> list[RevenueSignal]:
        """Poll Stripe for recent payment events."""
        if not self.stripe_key:
            return [RevenueSignal(
                source='stripe', signal_type='system_offline',
                value_usd=0, confidence=1.0,
                action_required='Add STRIPE_SECRET_KEY secret',
                urgency='high', timestamp=datetime.now(timezone.utc).isoformat(),
                metadata={'error': 'No Stripe key configured'}
            )]
        
        try:
            resp = requests.get(
                'https://api.stripe.com/v1/events?limit=10&type=payment_intent.succeeded',
                auth=(self.stripe_key, ''),
                timeout=10
            )
            if resp.status_code == 200:
                events = resp.json().get('data', [])
                signals = []
                for event in events:
                    amount = event.get('data', {}).get('object', {}).get('amount', 0)
                    signals.append(RevenueSignal(
                        source='stripe',
                        signal_type='revenue_confirmed',
                        value_usd=amount / 100,
                        confidence=1.0,
                        action_required='Record in Notion revenue log',
                        urgency='low',
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        metadata={'event_id': event.get('id', ''), 'type': event.get('type', '')}
                    ))
                return signals
        except Exception as e:
            pass
        return []
    
    def check_hubspot_pipeline(self) -> list[RevenueSignal]:
        """Check HubSpot for deal pipeline opportunities."""
        if not self.hubspot_key:
            return []
        try:
            resp = requests.post(
                'https://api.hubapi.com/crm/v3/objects/deals/search',
                headers={'Authorization': f'Bearer {self.hubspot_key}', 'Content-Type': 'application/json'},
                json={
                    'filterGroups': [{'filters': [{'propertyName': 'dealstage', 'operator': 'EQ', 'value': 'appointmentscheduled'}]}],
                    'limit': 10,
                    'properties': ['dealname', 'amount', 'dealstage', 'closedate']
                },
                timeout=10
            )
            if resp.status_code == 200:
                deals = resp.json().get('results', [])
                return [RevenueSignal(
                    source='hubspot',
                    signal_type='opportunity',
                    value_usd=float(d['properties'].get('amount', 0) or 0),
                    confidence=0.75,
                    action_required='Schedule follow-up call',
                    urgency='high',
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    metadata={'deal': d['properties'].get('dealname', ''), 'stage': d['properties'].get('dealstage', '')}
                ) for d in deals]
        except Exception:
            pass
        return []
    
    def broadcast(self, message: str, urgency: str = 'low'):
        """Broadcast signal to Slack."""
        if not self.slack_webhook:
            print(f"[BROADCAST] {message}")
            return
        emoji = '🚨' if urgency == 'immediate' else '⚠️' if urgency == 'high' else '💡'
        try:
            requests.post(self.slack_webhook, json={'text': f"{emoji} *REVENUE ENGINE* | {message}"}, timeout=5)
        except Exception:
            pass
    
    def run_cycle(self) -> dict:
        """Execute one full RHNS intelligence cycle."""
        print(f"[{datetime.now(timezone.utc).isoformat()}] Starting RHNS Revenue Intelligence Cycle...")
        
        # Collect signals
        raw_signals = []
        raw_signals.extend(self.check_stripe())
        raw_signals.extend(self.check_hubspot_pipeline())
        
        if not raw_signals:
            raw_signals.append(RevenueSignal(
                source='system', signal_type='heartbeat',
                value_usd=0, confidence=1.0,
                action_required='none', urgency='low',
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata={'cycle': 'nominal'}
            ))
        
        # RHNS Processing
        harmonized = self.harmonize(raw_signals)
        
        results = []
        for signal in harmonized:
            action = self.navigate(signal)
            verdict = self.enforce_standards(action, signal)
            results.append(verdict)
            
            if verdict['approved'] and signal.urgency in ('immediate', 'high'):
                self.broadcast(f"{action} | Confidence: {signal.confidence:.0%}", signal.urgency)
        
        # Write output
        output = {
            'cycle_time': datetime.now(timezone.utc).isoformat(),
            'signals_processed': len(harmonized),
            'actions_approved': sum(1 for r in results if r['approved']),
            'results': results
        }
        
        os.makedirs('output', exist_ok=True)
        with open(f"output/cycle-{int(time.time())}.json", 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"Cycle complete: {len(harmonized)} signals → {output['actions_approved']} actions approved")
        return output


if __name__ == '__main__':
    engine = RHNSRevenueEngine()
    result = engine.run_cycle()
    print(json.dumps(result, indent=2))
