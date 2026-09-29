/**
 * Rent Me design tokens, taken from the Rent Me Brand Guideline v1.0 (Sep 2026).
 */

export const Colors = {
  primary: '#0D6EFD', // Electric Blue — primary brand colour
  navy: '#0F172A', // Deep Navy — wordmark, headings, roof
  white: '#FFFFFF',
  background: '#FFFFFF',
  surface: '#F5F8FF', // light blue-grey page tint
  chip: '#EEF4FF', // tinted chip / pill background
  border: '#E5EAF2',
  text: '#0F172A',
  textSecondary: '#64748B',
  textMuted: '#94A3B8',
  success: '#16A34A',
  danger: '#DC2626',
} as const;

/** Manrope weights, loaded in the root layout. */
export const Fonts = {
  regular: 'Manrope_400Regular',
  medium: 'Manrope_500Medium',
  semibold: 'Manrope_600SemiBold',
  bold: 'Manrope_700Bold',
  extrabold: 'Manrope_800ExtraBold',
} as const;

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  pill: 999,
} as const;

export const Shadow = {
  card: {
    shadowColor: '#0F172A',
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 3,
  },
} as const;
