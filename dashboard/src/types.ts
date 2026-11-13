export interface ClaimItem {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  amount_claimed: number;
  items: ClaimItem[];
  documents: ClaimDocument[];
  status: "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";
  decision: string | null;
  payout: number | null;
  reason: string | null;
  policy_section: string | null;
  paid: boolean;
  signed_off: boolean;
  agent_reply?: string;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
  plan_details?: Record<string, number | string>;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  date_of_birth: string;
  address: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface ClaimActivity {
  id: number;
  claim_id: string;
  timestamp: string;
  action: string;
}
