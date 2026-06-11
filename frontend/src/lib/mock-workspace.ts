export const MOCK_PROJECT_NAME = "Acme GTM";

export interface MockPipeline {
  id: string;
  source: string;
  destination: string;
  status: "review" | "active" | "draft";
  stepsComplete: number;
  stepsTotal: number;
}

export interface MockConnector {
  id: string;
  name: string;
  icon: string;
  authenticated: boolean;
}

export interface MockActivityItem {
  id: string;
  label: string;
  status: "done" | "pending" | "waiting";
  time?: string;
}

export interface MockFieldMapping {
  sourceField: string;
  destinationField: string;
  note?: string;
}

export const MOCK_PIPELINES: MockPipeline[] = [
  {
    id: "sf-meta",
    source: "Salesforce",
    destination: "Meta",
    status: "review",
    stepsComplete: 4,
    stepsTotal: 5,
  },
  {
    id: "zoho-tiktok",
    source: "Zoho",
    destination: "TikTok",
    status: "active",
    stepsComplete: 5,
    stepsTotal: 5,
  },
];

export const MOCK_CONNECTORS: MockConnector[] = [
  { id: "salesforce", name: "Salesforce", icon: "SF", authenticated: true },
  { id: "meta", name: "Meta", icon: "M", authenticated: true },
  { id: "zoho", name: "Zoho", icon: "Z", authenticated: true },
];

export const MOCK_ACTIVITY: MockActivityItem[] = [
  { id: "1", label: "Connected to Salesforce", status: "done", time: "2m ago" },
  { id: "2", label: "OAuth token validated", status: "done", time: "1m ago" },
  { id: "3", label: "Field mapping proposed", status: "pending", time: "Just now" },
  { id: "4", label: "Test event — waiting for approval", status: "waiting" },
  { id: "5", label: "Go live — waiting for approval", status: "waiting" },
];

export const MOCK_FIELD_MAPPINGS: MockFieldMapping[] = [
  { sourceField: "Email", destinationField: "em" },
  { sourceField: "Phone", destinationField: "ph" },
  { sourceField: "First Name", destinationField: "fn" },
  { sourceField: "Last Name", destinationField: "ln" },
  { sourceField: "City", destinationField: "ct" },
  { sourceField: "Lead Source", destinationField: "—", note: "needs input" },
];
