export type PropertyType = 'house' | 'apartment' | 'room' | 'office' | 'commercial' | 'land';

export type ListerKind = 'landlord' | 'agent';

export type Property = {
  id: string;
  title: string;
  type: PropertyType;
  /** Monthly rent in Pula. */
  price: number;
  suburb: string;
  town: string;
  bedrooms: number;
  bathrooms: number;
  areaM2: number;
  garages: number;
  description: string;
  featured: boolean;
  lister: { name: string; kind: ListerKind };
};

export const PROPERTY_TYPE_LABELS: Record<PropertyType, string> = {
  house: 'House',
  apartment: 'Apartment',
  room: 'Room',
  office: 'Office',
  commercial: 'Commercial',
  land: 'Land',
};

export function formatPula(amount: number) {
  return `P${amount.toLocaleString('en-US')}`;
}

/**
 * Sample listings used until the Supabase backend is connected.
 */
export const SAMPLE_PROPERTIES: Property[] = [
  {
    id: 'p1',
    title: '2 Bedroom House',
    type: 'house',
    price: 4800,
    suburb: 'Block 10',
    town: 'Gaborone',
    bedrooms: 2,
    bathrooms: 1,
    areaM2: 120,
    garages: 1,
    description:
      'Modern 2 bedroom house in a secure estate in Block 10. Spacious living area, fitted kitchen, private yard and covered parking. Close to shops, schools and main roads.',
    featured: true,
    lister: { name: 'Neo Properties', kind: 'agent' },
  },
  {
    id: 'p2',
    title: '2 Bedroom House',
    type: 'house',
    price: 5000,
    suburb: 'Tlokweng',
    town: 'Gaborone',
    bedrooms: 2,
    bathrooms: 2,
    areaM2: 150,
    garages: 1,
    description:
      'Family home with two en-suite bedrooms, a large garden and borehole water. Quiet street, 10 minutes from the CBD.',
    featured: false,
    lister: { name: 'Kabo Molefe', kind: 'landlord' },
  },
  {
    id: 'p3',
    title: '2 Bedroom Apartment',
    type: 'apartment',
    price: 4500,
    suburb: 'Fairgrounds',
    town: 'Gaborone',
    bedrooms: 2,
    bathrooms: 1,
    areaM2: 95,
    garages: 0,
    description:
      'Furnished apartment walking distance from Fairgrounds offices. Balcony, backup water tank and 24-hour security.',
    featured: true,
    lister: { name: 'Property Connect', kind: 'agent' },
  },
  {
    id: 'p4',
    title: '2 Bedroom House',
    type: 'house',
    price: 4800,
    suburb: 'Phakalane',
    town: 'Gaborone',
    bedrooms: 2,
    bathrooms: 2,
    areaM2: 140,
    garages: 2,
    description:
      'Neat townhouse in a golf estate with a shared pool, double garage and fibre internet.',
    featured: false,
    lister: { name: 'Lerato Real Estate', kind: 'agent' },
  },
  {
    id: 'p5',
    title: '1 Bedroom Apartment',
    type: 'apartment',
    price: 3200,
    suburb: 'Block 8',
    town: 'Gaborone',
    bedrooms: 1,
    bathrooms: 1,
    areaM2: 60,
    garages: 0,
    description: 'Compact, affordable apartment ideal for a young professional. Prepaid electricity.',
    featured: false,
    lister: { name: 'Thato Kgosi', kind: 'landlord' },
  },
  {
    id: 'p6',
    title: 'Room near University',
    type: 'room',
    price: 1800,
    suburb: 'Extension 10',
    town: 'Gaborone',
    bedrooms: 1,
    bathrooms: 1,
    areaM2: 18,
    garages: 0,
    description: 'Furnished student room, 5 minutes walk from UB. Wi-Fi and water included.',
    featured: false,
    lister: { name: 'Mpho Seretse', kind: 'landlord' },
  },
  {
    id: 'p7',
    title: '3 Bedroom House',
    type: 'house',
    price: 6900,
    suburb: 'Broadhurst',
    town: 'Gaborone',
    bedrooms: 3,
    bathrooms: 2,
    areaM2: 180,
    garages: 1,
    description: 'Spacious family house with a big yard, servant quarters and solar geyser.',
    featured: true,
    lister: { name: 'Homefind BW', kind: 'agent' },
  },
  {
    id: 'p8',
    title: 'Office Space',
    type: 'office',
    price: 8500,
    suburb: 'CBD',
    town: 'Gaborone',
    bedrooms: 0,
    bathrooms: 1,
    areaM2: 110,
    garages: 2,
    description: 'Open-plan office on the second floor with boardroom and two parking bays.',
    featured: false,
    lister: { name: 'Motswedio Properties', kind: 'agent' },
  },
  {
    id: 'p9',
    title: '2 Bedroom Flat',
    type: 'apartment',
    price: 3800,
    suburb: 'Area W',
    town: 'Francistown',
    bedrooms: 2,
    bathrooms: 1,
    areaM2: 80,
    garages: 0,
    description: 'Tidy flat close to Galo Mall and the hospital. Water included.',
    featured: false,
    lister: { name: 'Onalenna Dube', kind: 'landlord' },
  },
  {
    id: 'p10',
    title: '3 Bedroom House',
    type: 'house',
    price: 5500,
    suburb: 'Boseja',
    town: 'Maun',
    bedrooms: 3,
    bathrooms: 2,
    areaM2: 160,
    garages: 1,
    description: 'Thatched family home with a large shady yard, a short drive from the airport.',
    featured: false,
    lister: { name: 'Delta Homes', kind: 'agent' },
  },
];
