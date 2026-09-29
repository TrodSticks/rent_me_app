import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { PropertyImage } from '@/components/property-image';
import { Colors, Fonts, Radius, Shadow } from '@/constants/theme';
import { formatPula, type Property } from '@/data/properties';

type Props = {
  property: Property;
  saved?: boolean;
  onToggleSave?: () => void;
  onPress?: () => void;
};

/** Horizontal listing card used on Home, Search Results and Saved. */
export function PropertyCard({ property, saved = false, onToggleSave, onPress }: Props) {
  return (
    <Pressable style={styles.card} onPress={onPress} accessibilityRole="button">
      <View>
        <PropertyImage type={property.type} style={styles.image} />
        <Pressable
          style={styles.heart}
          onPress={onToggleSave}
          hitSlop={8}
          accessibilityLabel={saved ? 'Remove from saved' : 'Save property'}>
          <Ionicons
            name={saved ? 'heart' : 'heart-outline'}
            size={16}
            color={saved ? Colors.primary : Colors.navy}
          />
        </Pressable>
      </View>
      <View style={styles.body}>
        <Text style={styles.price}>
          {formatPula(property.price)}
          <Text style={styles.per}> / month</Text>
        </Text>
        <Text style={styles.title} numberOfLines={1}>
          {property.title}
        </Text>
        <Text style={styles.location} numberOfLines={1}>
          {property.suburb}, {property.town}
        </Text>
        <View style={styles.specs}>
          {property.bedrooms > 0 && <Spec icon="bed-outline" label={`${property.bedrooms}`} />}
          {property.bathrooms > 0 && <Spec icon="water-outline" label={`${property.bathrooms}`} />}
          <Spec icon="expand-outline" label={`${property.areaM2} m²`} />
        </View>
      </View>
      <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
    </Pressable>
  );
}

function Spec({ icon, label }: { icon: keyof typeof Ionicons.glyphMap; label: string }) {
  return (
    <View style={styles.spec}>
      <Ionicons name={icon} size={13} color={Colors.textSecondary} />
      <Text style={styles.specText}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 8,
    paddingRight: 12,
    borderRadius: Radius.lg,
    backgroundColor: Colors.white,
    ...Shadow.card,
  },
  image: { width: 110, height: 96, borderRadius: Radius.md },
  heart: {
    position: 'absolute',
    top: 6,
    right: 6,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: { flex: 1, gap: 2 },
  price: { fontFamily: Fonts.extrabold, fontSize: 18, color: Colors.primary },
  per: { fontFamily: Fonts.medium, fontSize: 12 },
  title: { fontFamily: Fonts.bold, fontSize: 14, color: Colors.text },
  location: { fontFamily: Fonts.regular, fontSize: 12, color: Colors.textSecondary },
  specs: { flexDirection: 'row', gap: 12, marginTop: 6 },
  spec: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  specText: { fontFamily: Fonts.medium, fontSize: 12, color: Colors.textSecondary },
});
