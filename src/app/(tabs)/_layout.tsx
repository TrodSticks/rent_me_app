import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router/tabs';

import { Colors, Fonts } from '@/constants/theme';

type IconName = keyof typeof Ionicons.glyphMap;

const TABS: { name: string; title: string; icon: IconName; iconActive: IconName }[] = [
  { name: 'home', title: 'Home', icon: 'home-outline', iconActive: 'home' },
  { name: 'saved', title: 'Saved', icon: 'heart-outline', iconActive: 'heart' },
  { name: 'bookings', title: 'Bookings', icon: 'calendar-outline', iconActive: 'calendar' },
  { name: 'profile', title: 'Profile', icon: 'person-outline', iconActive: 'person' },
];

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.textSecondary,
        tabBarLabelStyle: { fontFamily: Fonts.semibold, fontSize: 11 },
        tabBarStyle: { borderTopColor: Colors.border, backgroundColor: Colors.white },
      }}>
      {TABS.map((t) => (
        <Tabs.Screen
          key={t.name}
          name={t.name}
          options={{
            title: t.title,
            tabBarIcon: ({ color, focused, size }) => (
              <Ionicons name={focused ? t.iconActive : t.icon} size={size} color={color} />
            ),
          }}
        />
      ))}
    </Tabs>
  );
}
