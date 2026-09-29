import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Logo } from '@/components/logo';
import { PropertyCard } from '@/components/property-card';
import { SearchBox } from '@/components/search-box';
import { Colors, Fonts, Radius } from '@/constants/theme';
import { SAMPLE_PROPERTIES } from '@/data/properties';
import { SUGGESTIONS } from '@/lib/search';
import { useSession } from '@/lib/session';

/** 03 · Home — plain-language search. */
export default function Home() {
  const { user, savedIds, toggleSaved } = useSession();
  const [query, setQuery] = useState('');
  const featured = SAMPLE_PROPERTIES.filter((p) => p.featured);

  const runSearch = (q: string) => {
    if (!q.trim()) return;
    router.push({ pathname: '/search', params: { q: q.trim() } });
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Logo size={26} />
          <View style={styles.headerRight}>
            <Pressable hitSlop={8} accessibilityLabel="Notifications">
              <Ionicons name="notifications-outline" size={24} color={Colors.navy} />
            </Pressable>
            <Pressable
              style={styles.avatar}
              accessibilityLabel={user ? 'Profile' : 'Sign in'}
              onPress={() => router.push(user ? '/profile' : '/sign-in')}>
              {user ? (
                <Text style={styles.avatarText}>{user.name.charAt(0).toUpperCase()}</Text>
              ) : (
                <Ionicons name="person" size={18} color={Colors.primary} />
              )}
            </Pressable>
          </View>
        </View>

        <Text style={styles.headline}>What are you{'\n'}looking for?</Text>
        <Text style={styles.sub}>
          Describe your ideal place in natural language. Be specific or keep it simple.
        </Text>

        <SearchBox value={query} onChangeText={setQuery} onSubmit={() => runSearch(query)} />

        <View style={styles.chips}>
          {SUGGESTIONS.map((s) => (
            <Pressable key={s} style={styles.chip} onPress={() => runSearch(s)}>
              <Text style={styles.chipText}>{s}</Text>
            </Pressable>
          ))}
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Featured Properties</Text>
          <Text style={styles.seeAll} onPress={() => runSearch('all properties')}>
            See all
          </Text>
        </View>
        <View style={{ gap: 12 }}>
          {featured.map((p) => (
            <PropertyCard
              key={p.id}
              property={p}
              saved={savedIds.has(p.id)}
              onToggleSave={() => toggleSaved(p.id)}
            />
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  scroll: { padding: 20, paddingBottom: 32 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  avatar: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: Colors.chip,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontFamily: Fonts.bold, fontSize: 16, color: Colors.primary },
  headline: {
    fontFamily: Fonts.extrabold,
    fontSize: 34,
    lineHeight: 40,
    letterSpacing: -0.8,
    color: Colors.text,
    marginTop: 28,
  },
  sub: {
    fontFamily: Fonts.regular,
    fontSize: 15,
    lineHeight: 22,
    color: Colors.textSecondary,
    marginTop: 8,
    marginBottom: 20,
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 18 },
  chip: {
    backgroundColor: Colors.chip,
    borderRadius: Radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  chipText: { fontFamily: Fonts.medium, fontSize: 13, color: Colors.navy },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 28,
    marginBottom: 12,
  },
  sectionTitle: { fontFamily: Fonts.bold, fontSize: 18, color: Colors.text },
  seeAll: { fontFamily: Fonts.semibold, fontSize: 14, color: Colors.primary },
});
