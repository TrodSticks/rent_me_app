import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button } from '@/components/button';
import { Logo } from '@/components/logo';
import { Colors, Fonts } from '@/constants/theme';

/** 01 · Splash / welcome screen. */
export default function Welcome() {
  return (
    <LinearGradient colors={['#1E3A8A', Colors.navy, '#060B17']} style={styles.fill}>
      <StatusBar style="light" />
      <SafeAreaView style={styles.safe}>
        <View>
          <Logo size={40} variant="dark" />
          <Text style={styles.headline}>Find a place.{'\n'}Call it home.</Text>
        </View>

        <View style={styles.bottom}>
          <Text style={styles.blurb}>
            Houses, apartments and rooms{'\n'}for rent across Botswana.
          </Text>
          <Button title="Get Started" onPress={() => router.push('/sign-up')} />
          <Button
            title="Sign In"
            variant="outlineLight"
            onPress={() => router.push('/sign-in')}
          />
          <Text style={styles.browse} onPress={() => router.replace('/home')}>
            Browse without an account
          </Text>
        </View>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  safe: { flex: 1, justifyContent: 'space-between', padding: 24 },
  headline: {
    fontFamily: Fonts.bold,
    fontSize: 28,
    lineHeight: 36,
    color: Colors.white,
    marginTop: 28,
  },
  bottom: { gap: 14 },
  blurb: { fontFamily: Fonts.medium, fontSize: 15, lineHeight: 22, color: '#CBD5E1', marginBottom: 8 },
  browse: {
    fontFamily: Fonts.semibold,
    fontSize: 14,
    color: '#CBD5E1',
    textAlign: 'center',
    paddingVertical: 6,
  },
});
