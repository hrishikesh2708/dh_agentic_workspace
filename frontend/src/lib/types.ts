// Mirrors backend Pydantic shapes from app/schemas/.

export interface User {
  user_id: string;
  email?: string;
  exp: number;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export interface UserResponse {
  id: number;
  email: string;
  username: string | null;
  token: Token;
}

export interface SessionResponse {
  session_id: string;
  name: string;
  token: Token;
}

export interface FieldMappingRead {
  id: number;
  session_id: number;
  source_field: string;
  destination_field: string | null;
  confidence: number;
  status: string;
  reasoning: string;
  transformation: string | null;
  validation_status: string;
  validation_notes: string[];
  created_at: string;
}

export interface MappingSessionRead {
  id: number;
  customer_id: number;
  source: string;
  source_object: string;
  destination_type: string;
  status: string;
  mapping_kind: string;
  canonical_session_id: number | null;
  created_at: string;
}

export interface MappingSessionDetail extends MappingSessionRead {
  field_mappings: FieldMappingRead[];
}

export interface MappingSessionListResponse {
  items: MappingSessionRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface GoldenRuleRead {
  id: number;
  source_pattern: string;
  destination_field: string;
  destination_type: string;
  occurrence_count: number;
  created_at: string;
}

export interface GoldenRuleCreate {
  source_pattern: string;
  destination_field: string;
  destination_type: string;
  occurrence_count?: number;
}

export interface GoldenRuleListResponse {
  items: GoldenRuleRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface SalesforceStatus {
  connected: boolean;
  auth_url: string;
}
