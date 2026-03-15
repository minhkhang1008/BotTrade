import React, { useEffect, useState } from 'react';
import { supabase } from '../supabase';

export const UserProfile: React.FC = () => {
  const [session, setSession] = useState<any>(null);
  const [isTelegramLinked, setIsTelegramLinked] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      checkTelegramStatus(session?.user?.id);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      checkTelegramStatus(session?.user?.id);
    });

    return () => subscription.unsubscribe();
  }, []);

  const checkTelegramStatus = async (userId: string | undefined) => {
    if (!userId) return;
    try {
      // Kiểm tra xem user này đã có telegram_chat_id trong DB chưa
      const { data } = await supabase.from('users').select('telegram_chat_id').eq('id', userId).single();
      if (data && data.telegram_chat_id) {
        setIsTelegramLinked(true);
      }
    } catch (error) {
      console.log("Đang chờ cập nhật liên kết Telegram...");
    }
  };

  const handleGoogleLogin = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin }
    });
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  if (!session) {
    return (
      <button 
        onClick={handleGoogleLogin}
        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition font-medium"
      >
        Đăng nhập bằng Google
      </button>
    );
  }

  const userId = session.user.id;
  // Nhớ đổi lại tên Bot của bạn ở đây nhé
  const telegramBotName = "entradex_autotrade_bot"; 
  const telegramLink = `https://web.telegram.org/a/#?tgaddr=tg%3A%2F%2Fresolve%3Fdomain%3D${telegramBotName}%26start%3D${userId}`;

  return (
    <div className="flex items-center gap-4 bg-gray-800 p-2 px-4 rounded-lg shadow-md border border-gray-700">
      <div className="text-sm text-gray-300">
        Hi, <b className="text-white">{session.user.email}</b>
      </div>
      
      {isTelegramLinked ? (
        <span className="px-3 py-1 bg-green-900/50 text-green-400 text-sm rounded-md border border-green-800 flex items-center gap-1">
          ✅ Đã kết nối Telegram
        </span>
      ) : (
        <a 
          href={telegramLink} 
          target="_blank" 
          rel="noopener noreferrer"
          className="px-3 py-1 bg-blue-500 text-white text-sm rounded-md hover:bg-blue-600 transition flex items-center gap-2"
        >
          📱 Kết nối Telegram
        </a>
      )}

      <button 
        onClick={handleLogout}
        className="px-3 py-1 bg-red-600/80 text-white text-sm rounded hover:bg-red-600 transition ml-2"
      >
        Thoát
      </button>
    </div>
  );
};