import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LogoMark } from '@/components/logo';
import { PropertyCard } from '@/components/property-card';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { SAMPLE_PROPERTIES, type PropertyType } from '@/data/properties';
import { describeSteps, search } from '@/lib/search';
import { smartSearch, type SmartSearchResult } from '@/lib/smart-search';
import { useSession } from '@/lib/session';

const FILTERS: { label: string; type: PropertyType | null }[] = [
  { label: 'All', type: null },
  { label: 'Houses', type: 'house' },
  { label: 'Apartments', type: 'apartment' },
  { label: 'Rooms', type: 'room' },
  { label: 'Offices', type: 'office' },
];

/** 04 · Search results for a plain-language query. */
export default function SearchResults() {
  const { q = '' } = useLocalSearchParams<{ q: string }>();
  const { savedIds, toggleSaved } = useSession();
  const [filter, setFilter] = useState<PropertyType | null>(null);

  // Show the instant rules result straight away; upgrade it if the LLM backup helps.
  const rules = useMemo(() => search(SAMPLE_PROPERTIES, q), [q]);
  const [smart, setSmart] = useState<{ q: string; result: SmartSearchResult } | null>(null);
  const thinking = smart?.q !== q;

  useEffect(() => {
    let cancelled = false;
    smartSearch(SAMPLE_PROPERTIES, q).then((result) => {
      if (!cancelled) setSmart({ q, result });
    });
    return () => {
      cancelled = true;
    };
  }, [q]);

  const result = !thinking && smart ? smart.result : rules;
  const { params, results } = result;
  const steps = describeSteps(params);
  const shown = filter ? results.filter((p) => p.type === filter) : results;

  const header = (
    <View>
      <View style={styles.bubbleRow}>
        <View style={styles.bubble}>
          <Text style={styles.bubbleText}>{q}</Text>
        </View>
      </View>

      <View style={styles.searching}>
        <LogoMark size={30} />
        <Text style={styles.searchingTitle}>Searching for you…</Text>
        {thinking && <ActivityIndicator size="small" color={Colors.primary} />}
      </View>
      <View style={styles.steps}>
        {steps.map((s) => (
          <View key={s} style={styles.step}>
            <Ionicons name="checkmark-circle" size={18} color={Colors.primary} />
            <Text style={styles.stepText}>{s}</Text>
          </View>
        ))}
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filters}>
        {FILTERS.map((f) => {
          const active = f.type === filter;
          return (
            <Pressable
              key={f.label}
              onPress={() => setFilter(f.type)}
              style={[styles.filter, active && styles.filterActive]}>
              <Text style={[styles.filterText, active && { color: Colors.white }]}>{f.label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>

      <Text style={styles.count}>
        {shown.length === 0
          ? 'No matching properties yet'
          : `Here ${shown.length === 1 ? 'is 1 matching property' : `are ${shown.length} matching properties`}`}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={12} accessibilityLabel="Back">
          <Ionicons name="chevron-back" size={24} color={Colors.navy} />
        </Pressable>
        <Text style={styles.topTitle}>Search</Text>
        <View style={{ width: 24 }} />
      </View>
      <FlatList
        data={shown}
        keyExtractor={(p) => p.id}
        ListHeaderComponent={header}
        contentContainerStyle={styles.list}
        ItemSeparatorComponent={() => <View style={{ height: 12 }} />}
        ListEmptyComponent={
          <Text style={styles.empty}>
            Try a different town, a higher budget or fewer details.
          </Text>
        }
        renderItem={({ item }) => (
          <PropertyCard
            property={item}
            saved={savedIds.has(item.id)}
            onToggleSave={() => toggleSaved(item.id)}
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 10,
  },
  topTitle: { fontFamily: Fonts.bold, fontSize: 18, color: Colors.text },
  list: { padding: 20, paddingTop: 8 },
  bubbleRow: { alignItems: 'flex-end' },
  bubble: {
    maxWidth: '85%',
    backgroundColor: Colors.chip,
    borderRadius: Radius.lg,
    borderTopRightRadius: 4,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  bubbleText: { fontFamily: Fonts.medium, fontSize: 15, lineHeight: 21, color: Colors.text },
  searching: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 20 },
  searchingTitle: { fontFamily: Fonts.bold, fontSize: 16, color: Colors.text },
  steps: {
    marginTop: 12,
    padding: 14,
    gap: 10,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  step: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  stepText: { fontFamily: Fonts.medium, fontSize: 14, color: Colors.textSecondary },
  filters: { gap: 8, paddingVertical: 18 },
  filter: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: Radius.pill,
    backgroundColor: Colors.chip,
  },
  filterActive: { backgroundColor: Colors.primary },
  filterText: { fontFamily: Fonts.semibold, fontSize: 13, color: Colors.navy },
  count: { fontFamily: Fonts.bold, fontSize: 16, color: Colors.text, marginBottom: 12 },
  empty: {
    fontFamily: Fonts.regular,
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginTop: 12,
  },
});
