import type { EstateState } from "./estate";

export interface PublicUser {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  relationship?: string | null;
  state?: string | null;
  county?: string | null;
  estateIds: string[];
  createdAt: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
  phone?: string | null;
  deceasedName: string;
  dateOfDeath?: string | null;
  relationship?: string | null;
  state?: string | null;
  county?: string | null;
  hasWill?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  user: PublicUser;
  estate?: EstateState | null;
}

export interface MeResponse {
  user: PublicUser;
  estates: EstateState[];
}
