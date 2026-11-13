interface Props {
  readonly policyId: string;
  readonly setPolicyId: (v: string) => void;
  readonly customerId: string;
  readonly setCustomerId: (v: string) => void;
  readonly claimType: string;
  readonly setClaimType: (v: string) => void;
  readonly incidentDate: string;
  readonly setIncidentDate: (v: string) => void;
  readonly incidentLocation: string;
  readonly setIncidentLocation: (v: string) => void;
  readonly amountClaimed: string;
  readonly setAmountClaimed: (v: string) => void;
  readonly summary: string;
  readonly setSummary: (v: string) => void;
  readonly story: string;
  readonly setStory: (v: string) => void;
}

export function ClaimFormFields(props: Props) {
  return (
    <>
      <div className="form-grid">
        <div className="form-group">
          <label htmlFor="policy-id" className="form-label">
            Policy ID *
          </label>
          <input
            id="policy-id"
            type="text"
            className="form-input"
            value={props.policyId}
            onChange={(e) => {
              props.setPolicyId(e.target.value);
            }}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="customer-id" className="form-label">
            Customer ID *
          </label>
          <input
            id="customer-id"
            type="text"
            className="form-input"
            value={props.customerId}
            onChange={(e) => {
              props.setCustomerId(e.target.value);
            }}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="claim-type" className="form-label">
            Claim Type *
          </label>
          <select
            id="claim-type"
            className="form-select"
            value={props.claimType}
            onChange={(e) => {
              props.setClaimType(e.target.value);
            }}
          >
            <option value="trip_delay">Trip Delay</option>
            <option value="trip_cancellation">Trip Cancellation</option>
            <option value="baggage_delay">Baggage Delay</option>
            <option value="baggage_loss">Baggage Loss</option>
            <option value="medical">Medical</option>
            <option value="personal_liability">Personal Liability</option>
          </select>
        </div>

        <div className="form-group">
          <label htmlFor="incident-date" className="form-label">
            Incident Date *
          </label>
          <input
            id="incident-date"
            type="date"
            className="form-input"
            value={props.incidentDate}
            onChange={(e) => {
              props.setIncidentDate(e.target.value);
            }}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="incident-location" className="form-label">
            Incident Location *
          </label>
          <input
            id="incident-location"
            type="text"
            placeholder="e.g. Rome, Italy"
            className="form-input"
            value={props.incidentLocation}
            onChange={(e) => {
              props.setIncidentLocation(e.target.value);
            }}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="amount-claimed" className="form-label">
            Amount Claimed ($ USD) *
          </label>
          <input
            id="amount-claimed"
            type="number"
            step="0.01"
            min="0.01"
            placeholder="0.00"
            className="form-input"
            value={props.amountClaimed}
            onChange={(e) => {
              props.setAmountClaimed(e.target.value);
            }}
            required
          />
        </div>
      </div>

      <div className="form-group" style={{ marginTop: "12px" }}>
        <label htmlFor="summary" className="form-label">
          Summary *
        </label>
        <input
          id="summary"
          type="text"
          placeholder="Brief summary of the incident"
          className="form-input"
          value={props.summary}
          onChange={(e) => {
            props.setSummary(e.target.value);
          }}
          required
        />
      </div>

      <div className="form-group" style={{ marginTop: "12px" }}>
        <label htmlFor="story" className="form-label">
          Customer Story *
        </label>
        <textarea
          id="story"
          rows={3}
          placeholder="Detailed explanation of what occurred..."
          className="form-textarea"
          value={props.story}
          onChange={(e) => {
            props.setStory(e.target.value);
          }}
          required
        />
      </div>
    </>
  );
}
