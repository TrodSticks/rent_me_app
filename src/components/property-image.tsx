import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, type ViewStyle } from 'react-native';

import type { PropertyType } from '@/data/properties';

const ICONS: Record<PropertyType, keyof typeof Ionicons.glyphMap> = {
  house: 'home',
  apartment: 'business',
  room: 'bed',
  office: 'briefcase',
  commercial: 'storefront',
  land: 'map',
};

/**
 * Stand-in for listing photos until uploads (Supabase Storage) are wired up.
 */
export function PropertyImage({ type, style }: { type: PropertyType; style?: ViewStyle }) {
  return (
    <LinearGradient colors={['#CFE0FF', '#8FB5F9']} style={[styles.box, style]}>
      <Ionicons name={ICONS[type]} size={36} color="rgba(255,255,255,0.9)" />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  box: { alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
});
