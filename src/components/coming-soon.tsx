import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts } from '@/constants/theme';

/** Placeholder for tabs that are built in a later step. */
export function ComingSoon({ title, icon }: { title: string; icon: keyof typeof Ionicons.glyphMap }) {
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.center}>
        <Ionicons name={icon} size={44} color={Colors.textMuted} />
        <Text style={styles.note}>Coming in the next build</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background, padding: 20 },
  title: { fontFamily: Fonts.extrabold, fontSize: 24, color: Colors.text },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  note: { fontFamily: Fonts.medium, fontSize: 14, color: Colors.textSecondary },
});
