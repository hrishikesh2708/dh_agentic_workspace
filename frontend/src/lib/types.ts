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

export interface ProjectRead {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string | null;
}

export interface ProjectListResponse {
  items: ProjectRead[];
  total: number;
}

// Used by HITL mapping cards in chat
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
