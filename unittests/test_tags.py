import logging
import random

from dojo.models import Finding, Product, Test
from dojo.product.helpers import propagate_tags_on_product_sync

from .dojo_test_case import DojoAPITestCase, get_unit_tests_scans_path

logger = logging.getLogger(__name__)


class TagTests(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self, *args, **kwargs):
        super().setUp()
        self.login_as_admin()
        self.scans_path = get_unit_tests_scans_path("zap")
        self.zap_sample5_filename = self.scans_path / "5_zap_sample_one.xml"

    def test_create_product_with_tags(self, expected_status_code: int = 201):
        product_id = Product.objects.all().first().id
        product_details = self.get_product_api(product_id)

        del product_details["id"]

        product_details["name"] = "tags test " + str(random.randint(1, 9999))  # noqa: S311
        product_details["tags"] = ["tag1", "tag2"]
        response = self.post_new_product_api(product_details, expected_status_code=expected_status_code)

        self.assertEqual(response["tags"], product_details["tags"])

    def test_put_product_with_tags(self):
        product_id = Product.objects.all().first().id
        product_details = self.get_product_api(product_id)

        del product_details["id"]

        product_details["name"] = "tags test " + str(random.randint(1, 9999))  # noqa: S311
        product_details["tags"] = ["tag4", "tag5"]
        response = self.put_product_api(product_id, product_details, expected_status_code=200)

        self.assertEqual(response["tags"], product_details["tags"])

    def test_patch_product_with_tags(self):
        product_id = Product.objects.all().first().id
        product_details = self.get_product_api(product_id)

        del product_details["id"]

        product_details["tags"] = ["tag9", "tag10"]
        response = self.patch_product_api(product_id, product_details, expected_status_code=200)

        self.assertEqual(response["tags"], product_details["tags"])

    def test_patch_product_with_invalid_tags(self):
        product_id = Product.objects.all().first().id

        product_details = {"tags": ["'tag9"]}
        self.patch_product_api(product_id, product_details, expected_status_code=400)
        product_details["tags"] = ["tag 10"]
        self.patch_product_api(product_id, product_details, expected_status_code=400)
        product_details["tags"] = ["tagA,tagB"]
        # since https://github.com/DefectDojo/django-DefectDojo/pull/12434 tags are split again by commas
        response = self.patch_product_api(product_id, product_details, expected_status_code=200)
        self.assertEqual(response["tags"], ["tagA", "tagB"])

    def create_finding_with_tags(self, tags: list[str], expected_status_code: int = 201):
        finding_id = Finding.objects.all().first().id
        finding_details = self.get_finding_api(finding_id)

        del finding_details["id"]

        finding_details["title"] = "tags test " + str(random.randint(1, 9999))  # noqa: S311
        finding_details["tags"] = tags
        response = self.post_new_finding_api(finding_details, expected_status_code=expected_status_code)

        return response["id"] if expected_status_code == 201 else 0

    def test_finding_get_tags(self):
        tags = ["tag1", "tag2"]
        finding_id = self.create_finding_with_tags(tags)
        response = self.get_finding_tags_api(finding_id)

        self.assertEqual(len(tags), len(response.get("tags", None)))
        for tag in tags:
            # logger.debug('looking for tag %s in tag list %s', tag, response['tags'])
            self.assertIn(tag, response["tags"])

    def test_finding_filter_tags(self):
        tags = ["tag1", "tag2"]
        self.create_finding_with_tags(tags)

        tags2 = ["tag1", "tag3"]
        self.create_finding_with_tags(tags2)

        response = self.get_finding_api_filter_tags("tag1")
        self.assertEqual(response["count"], 2)

        response = self.get_finding_api_filter_tags("tag2")
        self.assertEqual(response["count"], 1)

        response = self.get_finding_api_filter_tags("tag2,tag3")
        self.assertEqual(response["count"], 2)

        response = self.get_finding_api_filter_tags("tag4")
        self.assertEqual(response["count"], 0)
        # Test the tags__and filter for a case with no matches
        response = self.get_finding_api_filter_tags("tag2,tag3", parameter="tags__and")
        self.assertEqual(response["count"], 0)
        # Test the tags__and filter for a case with one exact match
        response = self.get_finding_api_filter_tags("tag1,tag2", parameter="tags__and")
        self.assertEqual(response["count"], 1)

    def test_finding_post_tags(self):
        # create finding
        tags = ["tag1", "tag2"]
        finding_id = self.create_finding_with_tags(tags)

        # post tags. POST will ADD tags to existing tags (which is possibly not REST compliant?)
        tags_new = ["tag3", "tag4"]
        response = self.post_finding_tags_api(finding_id, tags_new)
        tags_merged = list(set(tags) | set(tags_new))
        self.assertEqual(len(tags_merged), len(response.get("tags")))
        for tag in tags_merged:
            # logger.debug('looking for tag %s in tag list %s', tag, response['tags'])
            self.assertIn(tag, response["tags"])

    def test_finding_post_tags_overlap(self):
        # create finding
        tags = ["tag1", "tag2"]
        finding_id = self.create_finding_with_tags(tags)

        # post tags. POST will ADD tags to existing tags (which is possibly not REST compliant?)
        tags_new = ["tag2", "tag3"]
        response = self.post_finding_tags_api(finding_id, tags_new)
        tags_merged = list(set(tags) | set(tags_new))
        self.assertEqual(len(tags_merged), len(response.get("tags")))
        for tag in tags_merged:
            # logger.debug('looking for tag %s in tag list %s', tag, response['tags'])
            self.assertIn(tag, response["tags"])

    def test_finding_put_remove_tags(self):
        # create finding
        tags = ["tag1", "tag2"]
        finding_id = self.create_finding_with_tags(tags)

        # post tags. PUT will remove any tags that exist
        tags_remove = ["tag1"]
        response = self.put_finding_remove_tags_api(finding_id, tags_remove)

        # for some reason this method returns just a message, not the remaining tags
        self.assertEqual(response["success"], "Tag(s) Removed")

        # retrieve finding and check
        tags_merged = list(set(tags) - set(tags_remove))
        response = self.get_finding_tags_api(finding_id)
        self.assertEqual(len(tags_merged), len(response.get("tags")))
        for tag in tags_merged:
            # logger.debug('looking for tag %s in tag list %s', tag, response['tags'])
            self.assertIn(tag, response["tags"])

    def test_finding_put_remove_tags_all(self):
        # create finding
        tags = ["tag1", "tag2"]
        finding_id = self.create_finding_with_tags(tags)

        # post tags. PUT will remove any tags that exist
        tags_remove = tags
        response = self.put_finding_remove_tags_api(finding_id, tags_remove)

        # for some reason this method returns just a message, not the remaining tags
        self.assertEqual(response["success"], "Tag(s) Removed")

        # retrieve finding and check
        tags_merged = list(set(tags) - set(tags_remove))
        response = self.get_finding_tags_api(finding_id)
        self.assertEqual(len(tags_merged), len(response.get("tags")))
        for tag in tags_merged:
            # logger.debug('looking for tag %s in tag list %s', tag, response['tags'])
            self.assertIn(tag, response["tags"])

    def test_finding_put_remove_tags_non_existent(self):
        # create finding
        tags = ["tag1", "tag2"]
        finding_id = self.create_finding_with_tags(tags)

        # post tags. PUT will throw an error on non-existent tag to be removed (which is maybe not what we want?)
        tags_remove = ["tag5"]
        response = self.put_finding_remove_tags_api(finding_id, tags_remove, expected_response_status_code=400)

        # for some reason this method returns just a message, not the remaining tags
        self.assertEqual(response["error"], "'tag5' is not a valid tag in list '['tag1', 'tag2']'")

        # retrieve finding and check
        tags_merged = list(set(tags) - set(tags_remove))
        response = self.get_finding_tags_api(finding_id)
        self.assertEqual(len(tags_merged), len(response.get("tags")))
        for tag in tags_merged:
            # logger.debug('looking for tag %s in tag list %s', tag, response['tags'])
            self.assertIn(tag, response["tags"])

    def test_finding_patch_remove_tags(self):
        # has same logic as PUT
        return self.test_finding_put_remove_tags()

    def test_finding_patch_remove_tags_all(self):
        return self.test_finding_put_remove_tags_all()

    def test_finding_patch_remove_tags_non_existent(self):
        return self.test_finding_put_remove_tags_non_existent()

    def test_finding_create_tags_with_commas(self):
        tags = ["one,two"]
        finding_id = self.create_finding_with_tags(tags)
        response = self.get_finding_tags_api(finding_id)

        # since https://github.com/DefectDojo/django-DefectDojo/pull/12434 tags are split again by commas
        self.assertEqual(["one", "two"], response.get("tags"))
        self.assertEqual(2, len(response.get("tags")))
        self.assertIn("one", str(response["tags"]))
        self.assertIn("two", str(response["tags"]))

    def test_finding_create_tags_with_spaces(self):
        tags = ["one two"]
        self.create_finding_with_tags(tags, expected_status_code=400)

    def test_finding_create_tags_with_double_quotes(self):
        tags = ['"one-two"']
        self.create_finding_with_tags(tags, expected_status_code=400)

    def test_finding_create_tags_with_single_quotes(self):
        tags = ["'one-two'"]
        self.create_finding_with_tags(tags, expected_status_code=400)

    def test_finding_create_tags_with_slashes(self):
        tags = ["a/b/c"]
        finding_id = self.create_finding_with_tags(tags)
        response = self.get_finding_tags_api(finding_id)

        self.assertEqual(len(tags), len(response.get("tags", None)))
        for tag in tags:
            # logger.debug('looking for tag %s in tag list %s', tag, response['tags'])
            self.assertIn(tag, response["tags"])

    def test_import_and_reimport_with_tags(self):
        tags = ["tag1", "tag2"]
        import0 = self.import_scan_with_params(self.zap_sample5_filename, tags=tags)
        test_id = import0["test"]

        response = self.get_test_api(test_id)

        self.assertEqual(len(tags), len(response.get("tags")))
        for tag in tags:
            self.assertIn(tag, response["tags"])

        # reimport, do not specify tags: should retain tags
        self.reimport_scan_with_params(test_id, self.zap_sample5_filename)
        self.assertEqual(len(tags), len(response.get("tags")))
        for tag in tags:
            self.assertIn(tag, response["tags"])

        # reimport, specify tags others: currently reimport doesn't do anything with tags param and silently ignores them
        self.reimport_scan_with_params(test_id, self.zap_sample5_filename, tags=["tag3", "tag4"])
        self.assertEqual(len(tags), len(response.get("tags")))
        for tag in tags:
            self.assertIn(tag, response["tags"])

    def test_import_multipart_tags(self):
        with (self.zap_sample5_filename).open(encoding="utf-8") as testfile:
            data = {
                "engagement": [1],
                "file": [testfile],
                "scan_type": ["ZAP Scan"],
                "tags": ["bug,security", "urgent"],  # Attempting to mimic the two "tag" fields (-F 'tags=tag1' -F 'tags=tag2')
            }
            response = self.import_scan(data, 201)
            # Make sure the serializer returns the correct tags
            success_tags = ["bug", "security", "urgent"]
            self.assertEqual(response["tags"], success_tags)
            # Check that the test has the same issue
            test_id = response["test"]
            response = self.get_test_api(test_id)
            self.assertEqual(len(success_tags), len(response.get("tags")))
            for tag in success_tags:
                self.assertIn(tag, response["tags"])


class InheritedTagsTests(DojoAPITestCase):
    fixtures = ["dojo_testdata.json"]

    def setUp(self, *args, **kwargs):
        super().setUp()
        self.login_as_admin()
        self.system_settings(enable_product_tag_inehritance=True)
        self.product = self.create_product("Inherited Tags Test", tags=["inherit", "these", "tags"])
        self.scans_path = get_unit_tests_scans_path("zap")
        self.zap_sample5_filename = self.scans_path / "5_zap_sample_one.xml"

    def _convert_instance_tags_to_list(self, instance) -> list:
        return [tag.name for tag in instance.tags.all()]

    def _import_and_return_objects(self, test_id=None, *, reimport=False, tags=None) -> dict:
        # Import some findings to create all objects
        engagement = self.create_engagement("Inherited Tags Engagement", self.product)
        if reimport:
            response = self.reimport_scan_with_params(test_id, self.zap_sample5_filename, tags=tags)
        else:
            response = self.import_scan_with_params(self.zap_sample5_filename, engagement=engagement.id, tags=tags)

        test_id = response["test"]
        test = Test.objects.get(id=test_id)
        finding = Finding.objects.filter(test=test).first()
        endpoint = finding.endpoints.all().first()
        return {
            "engagement": engagement,
            "endpoint": endpoint,
            "test": test,
            "finding": finding,
        }

    def test_import_without_tags(self):
        # Import some findings to create all objects
        objects = self._import_and_return_objects()
        # Check that the tags all match what the product has
        product_tags = self._convert_instance_tags_to_list(self.product)
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("engagement")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("endpoint")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("test")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("finding")))

    def test_import_with_tags_then_reimport_with_different_tag(self):
        # Import some findings to create all objects
        objects = self._import_and_return_objects(tags=["import_tag"])
        # Check that the tags all match what the product has
        product_tags = self._convert_instance_tags_to_list(self.product)
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("engagement")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("endpoint")))
        self.assertEqual(["import_tag", *product_tags], self._convert_instance_tags_to_list(objects.get("test")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("finding")))
        # Reimport now
        objects = self._import_and_return_objects(test_id=objects.get("test").id, reimport=True, tags=["reimport_tag"])
        # Check that the tags all match what the product has
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("engagement")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("endpoint")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("finding")))
        # Make a copy of the list becase of the need for the lists to be exact (index for index)
        product_tags_plus_reimport_tag = product_tags.copy()
        product_tags_plus_reimport_tag.insert(1, "reimport_tag")
        self.assertEqual(product_tags_plus_reimport_tag, self._convert_instance_tags_to_list(objects.get("test")))

    def test_new_engagement_then_add_tag_to_engagement_then_remove_tag_to_engagement(self):
        # Create the engagement
        engagement = self.create_engagement("Inherited Tags Engagement", self.product)
        test = self.create_test(engagement=engagement, scan_type="ZAP Scan")
        # Check to see if tags match the product
        product_tags = self._convert_instance_tags_to_list(self.product)
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(engagement))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(test))
        # Add a tag on the engagement)
        engagement_tags_before_addition = self._convert_instance_tags_to_list(engagement)
        engagement.tags.add("engagement_only_tag")
        # Check to see that the update was successful
        self.assertEqual(["engagement_only_tag", *engagement_tags_before_addition], self._convert_instance_tags_to_list(engagement))
        # Check to see that tests were not impacted
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(test))
        # remove a tag on the engagement
        engagement_tags_before_removal = self._convert_instance_tags_to_list(engagement)
        engagement.tags.remove("engagement_only_tag")
        # Check to see that the update was successful
        engagement_tags_before_removal.remove("engagement_only_tag")
        self.assertEqual(engagement_tags_before_removal, self._convert_instance_tags_to_list(engagement))
        # Check to see that tests were not impacted
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(test))

    def test_new_engagement_then_remove_inherited_tag(self):
        # Create the engagement
        engagement = self.create_engagement("Inherited Tags Engagement", self.product)
        # Check to see if tags match the product
        product_tags = self._convert_instance_tags_to_list(self.product)
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(engagement))
        # Remove an inherited tag
        engagement_tags_before_removal = self._convert_instance_tags_to_list(engagement)
        engagement.tags.remove("inherit")
        # Check to see that the inherited tag could not be removed
        self.assertEqual(engagement_tags_before_removal, self._convert_instance_tags_to_list(engagement))

    def test_remove_tag_from_product_then_add_tag_to_product(self):
        # Import some findings to create all objects
        objects = self._import_and_return_objects()
        # Check that the tags all match what the product has
        product_tags = self._convert_instance_tags_to_list(self.product)
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("engagement")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("endpoint")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("test")))
        self.assertEqual(product_tags, self._convert_instance_tags_to_list(objects.get("finding")))
        # Remove a tag from the product
        self.product.tags.remove("inherit")
        # This triggers an async function with celery that will fail, so run it manually here
        propagate_tags_on_product_sync(self.product)
        # Save the tags post removal
        product_tags_post_removal = self._convert_instance_tags_to_list(self.product)
        # Check that the tags all match what the product has
        self.assertEqual(product_tags_post_removal, self._convert_instance_tags_to_list(objects.get("engagement")))
        self.assertEqual(product_tags_post_removal, self._convert_instance_tags_to_list(objects.get("endpoint")))
        self.assertEqual(product_tags_post_removal, self._convert_instance_tags_to_list(objects.get("test")))
        self.assertEqual(product_tags_post_removal, self._convert_instance_tags_to_list(objects.get("finding")))
        # Add a tag from the product
        self.product.tags.add("more", "tags!")
        # This triggers an async function with celery that will fail, so run it manually here
        propagate_tags_on_product_sync(self.product)
        # Save the tags post removal
        product_tags_post_addition = self._convert_instance_tags_to_list(self.product)
        # Check that the tags all match what the product has
        self.assertEqual(product_tags_post_addition, self._convert_instance_tags_to_list(objects.get("engagement")))
        self.assertEqual(product_tags_post_addition, self._convert_instance_tags_to_list(objects.get("endpoint")))
        self.assertEqual(product_tags_post_addition, self._convert_instance_tags_to_list(objects.get("test")))
        self.assertEqual(product_tags_post_addition, self._convert_instance_tags_to_list(objects.get("finding")))
