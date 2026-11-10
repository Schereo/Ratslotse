/* Piktogramme des „Kurses der Sitzung" — Plan, Anhang A. Der Server liefert
   den Schlüssel (`council/course.py::ICONS`), hier steht nur, welches
   Lucide-Zeichen dazu gehört. `tests/test_course.py` hält diese Tabelle,
   die des Servers und die des Plans gleich: Ein Schlüssel, der hier fehlt,
   fiele still auf das Dokument zurück. */

import {
  Anchor, Baby, Ban, Bike, Building2, Bus, ClipboardList, Drama, Droplets, Euro, FilePen, FileText,
  FlaskConical, Gauge, GraduationCap, HeartHandshake, House, Leaf, ListChecks, Lock, Map, Megaphone,
  MessageCircleQuestion, MessagesSquare, Plane, Route, Signpost, SquareParking, Ticket, Trash2, Trophy,
  UserPlus, Wind, Wrench, type LucideIcon,
} from "lucide-react";

export const COURSE_ICONS: Record<string, LucideIcon> = {
  formalities: ListChecks,
  citizen_question: MessageCircleQuestion,
  inquiries: MessagesSquare,
  announcement: Megaphone,
  sign: Signpost,
  bike: Bike,
  bus: Bus,
  ticket: Ticket,
  speed: Gauge,
  route: Route,
  parking: SquareParking,
  closure: Ban,
  building: Building2,
  housing: House,
  plan: Map,
  greenery: Leaf,
  water: Droplets,
  energy: Wind,
  waste: Trash2,
  money: Euro,
  environment: FlaskConical,
  renovation: Wrench,
  personnel: UserPlus,
  statute: FileText,
  airfield: Plane,
  school: GraduationCap,
  daycare: Baby,
  sport: Trophy,
  culture: Drama,
  social: HeartHandshake,
  report: ClipboardList,
  motion: FilePen,
};

/** Fest: Anker für den Beginn, Schloss für nichtöffentlich. */
export const COURSE_START_ICON = Anchor;
export const COURSE_LOCK_ICON = Lock;

export function courseIcon(key: string | null | undefined): LucideIcon {
  return (key && COURSE_ICONS[key]) || FileText;
}
