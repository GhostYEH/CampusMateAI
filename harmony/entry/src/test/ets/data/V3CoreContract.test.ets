import { describe, expect, it } from '@ohos/hypium';
import { AcademicStatusItem, CommunityPostPayload, UniversityItem } from '../../../main/ets/data/Models';

export default function v3CoreContractTest() {
  describe('V3CoreContract', () => {
    it('keeps university community and academic payloads aligned with backend', 0, () => {
      const university: UniversityItem = { id: 'uni-demo', name: 'Demo University', academic_provider: 'unsupported', forum_enabled: true, is_demo: true };
      const post: CommunityPostPayload = {
        title: '约自习',
        content: '图书馆见',
        category: 'campus',
        post_type: 'experience',
        sub_category: 'study',
        images: [],
        is_anonymous: false
      };
      const status: AcademicStatusItem = { status: 'unsupported', provider: 'unsupported' };
      expect(university.id).assertEqual('uni-demo');
      expect(post.category).assertEqual('campus');
      expect(post.images.length).assertEqual(0);
      expect(status.status).assertEqual('unsupported');
    });
  });
}
