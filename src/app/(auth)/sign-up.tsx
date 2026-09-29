import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { AuthPage, authStyles } from '@/components/form';
import { Colors, Fonts, Radius } from '@/constants/theme';

/** 02 · Sign Up — choose how to create an account. */
export default function SignUp() {
  const comingSoon = (provider: string) =>
    Alert.alert(
      `${provider} sign-in`,
      `${provider} sign-in will be switched on when the Supabase backend is connected. Use email for now.`,
    );

  return (
    <AuthPage>
      <Text style={authStyles.title}>Create your account</Text>
      <Text style={authStyles.subtitle}>
        Join Rent Me to find or list properties across Botswana.
      </Text>

      <View style={{ gap: 12 }}>
        <Provider icon="logo-google" label="Continue with Google" onPress={() => comingSoon('Google')} />
        <Provider icon="logo-apple" label="Continue with Apple" onPress={() => comingSoon('Apple')} />
        <Provider
          icon="mail-outline"
          iconColor={Colors.primary}
          label="Continue with Email"
          onPress={() => router.push('/sign-up-email')}
        />
      </View>

      <View style={{ flex: 1 }} />
      <Text style={authStyles.footer}>
        Already have an account?{' '}
        <Text style={authStyles.link} onPress={() => router.replace('/sign-in')}>
          Sign In
        </Text>
      </Text>
    </AuthPage>
  );
}

function Provider({
  icon,
  label,
  iconColor = Colors.navy,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  iconColor?: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [styles.provider, pressed && { backgroundColor: Colors.surface }]}>
      <Ionicons name={icon} size={20} color={iconColor} style={styles.providerIcon} />
      <Text style={styles.providerLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  provider: {
    height: 54,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.md,
    paddingHorizontal: 18,
    backgroundColor: Colors.white,
  },
  providerIcon: { width: 40 },
  providerLabel: { fontFamily: Fonts.semibold, fontSize: 15, color: Colors.text },
});
