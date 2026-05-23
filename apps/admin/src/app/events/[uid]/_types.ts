/* ------------------------------------------------------------------ */
/*  Shared types for Event Detail page                                 */
/* ------------------------------------------------------------------ */

export interface EventData {
  id: string;
  uid: string;
  name: string;
  description: string | null;
  date: string | null;
  end_date: string | null;
  is_active: boolean;
  background_image: string | null;
  branding_text: string | null;
  display_date: string | null;
  created_at: string;
  updated_at: string | null;
  photo_count?: number;
}

export interface PresetBackground {
  name: string;
  label: string;
  url: string;
  exists: boolean;
}

export type Tab = "general" | "photocard" | "sharing";
export type PreviewLayout = "single" | "strip" | "grid";

export interface EventForm {
  name: string;
  description: string;
  date: string;
  end_date: string;
  is_active: boolean;
}
