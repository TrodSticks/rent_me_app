import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import type { ReactNode } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Colors, Fonts, Radius } from '@/constants/theme';

/** Scrollable, keyboard-aware page with a back arrow — shared by the auth screens. */
export function AuthPage({ children }: { children: ReactNode }) {
  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Pressable
            onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))}
            hitSlop={12}
            accessibilityLabel="Back"
            style={styles.back}>
            <Ionicons name="chevron-back" size={24} color={Colors.navy} />
          </Pressable>
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function Field({ label, error, ...input }: TextInputProps & { label: string; error?: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        placeholderTextColor={Colors.textMuted}
        style={[styles.input, !!error && { borderColor: Colors.danger }]}
        {...input}
      />
      {!!error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

export const authStyles = StyleSheet.create({
  title: { fontFamily: Fonts.extrabold, fontSize: 26, color: Colors.text, marginTop: 24 },
  subtitle: {
    fontFamily: Fonts.regular,
    fontSize: 15,
    lineHeight: 22,
    color: Colors.textSecondary,
    marginTop: 8,
    marginBottom: 28,
  },
  footer: {
    fontFamily: Fonts.regular,
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginTop: 28,
  },
  link: { fontFamily: Fonts.bold, color: Colors.primary },
});

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  scroll: { flexGrow: 1, padding: 24 },
  back: { width: 32, height: 32, justifyContent: 'center' },
  field: { marginBottom: 16 },
  label: { fontFamily: Fonts.semibold, fontSize: 13, color: Colors.text, marginBottom: 6 },
  input: {
    height: 52,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    paddingHorizontal: 16,
    fontFamily: Fonts.medium,
    fontSize: 15,
    color: Colors.text,
    backgroundColor: Colors.white,
  },
  error: { fontFamily: Fonts.medium, fontSize: 12, color: Colors.danger, marginTop: 4 },
});
